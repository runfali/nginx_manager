import base64
import secrets
import zlib
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# 生成密码哈希
def get_password_hash(password):
    return pwd_context.hash(password)


# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def _derive_aes_key() -> bytes:
    salt = b"nginx_manager_ssh_salt"  # constant salt, ok for single-app dev
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return kdf.derive(settings.SECRET_KEY.encode())


_aes_key: Optional[bytes] = None


def _get_aes_key() -> bytes:
    global _aes_key
    if _aes_key is None:
        _aes_key = _derive_aes_key()
    return _aes_key


def encrypt_private_key(plaintext: Optional[str]) -> Optional[str]:
    if not plaintext:
        return plaintext
    key = _get_aes_key()
    compressed = zlib.compress(plaintext.encode())
    iv = secrets.token_bytes(16)
    padder = PKCS7(128).padder()
    padded = padder.update(compressed) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode()


def decrypt_private_key(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return ciphertext
    try:
        key = _get_aes_key()
        raw = base64.b64decode(ciphertext)
        iv, ct = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        plain = unpadder.update(padded) + unpadder.finalize()
        return zlib.decompress(plain).decode()
    except Exception:
        return ciphertext
