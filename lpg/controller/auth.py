import os

import jwt


def generate_jwt(user_id):
    payload = {'user_id': str(user_id)}
    return jwt.encode(payload, os.getenv('JWT_SECRET'), algorithm='HS256')


def verify_jwt(token):
    try:
        payload = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
