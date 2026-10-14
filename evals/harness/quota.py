"""Conservative durable free-capacity reservations; no automatic billing pathway."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path


class FreeQuota:
    def __init__(self, path: Path, model: str):
        self.path = path
        self.model = model
        value = self._read()
        self.rpm, self.tpm = value['requests_per_minute'], value['tokens_per_minute']
        self.max_concurrency = value['max_concurrency']
        self.remaining_calls = value['remaining_calls']

    def _read(self):
        value = json.loads(self.path.read_text(encoding='utf-8'))
        required = {'model', 'billing_disabled', 'additional_spend_limit', 'verification_reference', 'expires_at',
                    'remaining_calls', 'remaining_input_tokens', 'remaining_output_tokens', 'requests_per_minute', 'tokens_per_minute', 'max_concurrency'}
        if not required.issubset(value) or value['billing_disabled'] is not True or value['additional_spend_limit'] != 0:
            raise ValueError('A verified zero-spend quota ledger with disabled billing is required.')
        if value['model'] != self.model or not value['verification_reference']:
            raise ValueError('Quota verification does not match the selected model.')
        expires = datetime.fromisoformat(value['expires_at'].replace('Z', '+00:00'))
        if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
            raise ValueError('Free-quota verification has expired.')
        for key in ('remaining_calls', 'remaining_input_tokens', 'remaining_output_tokens', 'requests_per_minute', 'tokens_per_minute', 'max_concurrency'):
            if type(value[key]) is not int or value[key] < (1 if key in ('requests_per_minute', 'tokens_per_minute', 'max_concurrency') else 0):
                raise ValueError('Invalid free-quota limit.')
        return value

    def reserve(self, attempt_id, calls):
        lock = self.path.with_suffix(self.path.suffix + '.lock')
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError('Quota ledger is locked. Verify its owner process before manual recovery.') from None
        try:
            os.close(handle)
            value = self._read()
            bounds = {'remaining_calls': calls, 'remaining_input_tokens': 11000, 'remaining_output_tokens': 4000}
            if any(value[key] < amount for key, amount in bounds.items()):
                raise ValueError('Verified free capacity is insufficient; no model request was sent.')
            for key, amount in bounds.items(): value[key] -= amount
            value.setdefault('reservations', []).append({'attempt_id': attempt_id, 'calls_bound': calls, 'input_bound': 11000, 'output_bound': 4000, 'at': datetime.now(timezone.utc).isoformat()})
            temporary = self.path.with_suffix(self.path.suffix + '.next')
            with temporary.open('w', encoding='utf-8') as file:
                file.write(json.dumps(value, indent=2) + '\n')
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            lock.unlink()
