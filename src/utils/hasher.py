from werkzeug.security import generate_password_hash, check_password_hash


def generate_hash(password: str) -> str:
    """ Генерация хэша пароля """
    return generate_password_hash(password=password)


def check_hash(hash: str, password: str) -> bool:
    """ Проверка хэша пароля """
    return check_password_hash(pwhash=hash, password=password)
