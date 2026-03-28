from typing import Protocol


class PasswordHasher(Protocol):
    def hash_password(self, password: str) -> str:
        pass

    def verify_password(self, password: str, password_hash: str) -> bool:
        pass


class BcryptPasswordHasher:
    def __init__(self, rounds: int = 12) -> None:
        self.rounds = rounds

    def _get_bcrypt(self):
        import bcrypt

        return bcrypt

    def hash_password(self, password: str) -> str:
        bcrypt = self._get_bcrypt()
        salt = bcrypt.gensalt(rounds=self.rounds)
        password_bytes = password.encode("utf-8")
        return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        bcrypt = self._get_bcrypt()
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
