import hashlib
import hmac
import os
import secrets
from pathlib import Path
from turtledemo.sorting_animate import start_ssort

import gridfs
import mysql.connector
from bson import ObjectId
from pymongo import MongoClient, cursor


def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"

def _password_is_correct(password, saved_hash):
    try:
        salt_hex, digest_hex = saved_hash.split("$", 1)
        actual_hash = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(actual_hash, digest_hex)
    except (AttributeError, ValueError):
        return False

class Database:
    def __init__(self):
        self.mysql = mysql.connector.connect(
            host="127.0.0.1", port=3306, user="root", passwd="123123", database="4vito"
        )

        self.mongo_client = MongoClient("mongodb://localhost:27017")
        self.mongo_db =self.mongo_client["4vito"]
        self.files = gridfs.GridFS(self.mongo_db)

    def register(self, login, email, password):
        cursor = self.mysql.cursor()
        try:
            cursor.execute(
            "SELECT id_user FROM users WHERE name = %s OR email = %s",
            (login, email.lower()),
        )
            if cursor.fetchone():
                raise ValueError("Этот логи или email уже существуют")
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (login, email.lower(), _hash_password(password)),
            )
            self.mysql.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
    def login(self, login_or_email, password):
        cursor = self.mysql.cursor(dictionary=True)
        try:
            cursor.execute(
                "select id_users as id, name, email, password from users "
                "where email - %s or name = %s",
                (login_or_email.lower(), login_or_email),
            )
            user = cursor.fetchone()
            if not user:
                return None

            saved_password = user.pop("password")
            if _password_is_correct(password, saved_password):
                return user
            return None
        finally:
            cursor.close()

    def add(self, user_id, title, description, price, category, photo_paths):
        photo_ids = []
        try:
            for path in photo_paths:
                with open(path, "rb") as image:
                    photo_id = self.files.put(image, filename=Path(path).name)
                    photo_ids.append(str(photo_id))

            cursor = self.mysql.cursor()
            try:
                cursor.execute(
                    "insert into product"
                    "(user_id, title, description, price, category, photos, photo_ids) "
                    "values (%s, %s, %s, %s, %s, active, %s)",
                    (user_id, title, description, price, category, ",".join(photo_ids)),
                )
                self.mysql.commit()
            finally:
                cursor.close()
        except Exception:
            self.delete_photos(photo_ids)
            raise

    def product(self, user_id=None):
        cursor = self.mysql.cursor(dictionary=True)
        try:
            query = """
                product.id_product AS id, product.user_id,
                       product.title, product.description, product.price,
                       product.category, product.photo_ids,
                       COALESCE(users.name, 'Продавец') AS seller
                from product
                left join users on users.id_user = product.user_id
                where product.status='active'
            """
            params = ()
            if user_id is not None:
                query += "and product.user_id = %s"
                params = (user_id,)
            query += "order by product.id_product desc"
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_photo(self, photo_id):
        return self.files.get(ObjectId(photo_id)).read()

    def delete_ad(self, ad_id, owner_id):
        cursor = self.mysql.cursor(dictionary=True)
        try:
            cursor.execute(
                "select photo_ids from product"
                "where id_product = %s and user_id = %s",
                (ad_id, owner_id),
            )
            product = cursor.fetchone()
            if not product:
                return False

            cursor.execute(
                "delete from product where id_product = %s and user_id = %s",
                (ad_id, owner_id),
            )
            self.mysql.commit()
        finally:
            cursor.close()

        self.delete_photos((product["photo_ids"] or "").split(","))
        return True

    def order_ad(self, ad_id, buyer_id):
        cursor = self.mysql.cursor()
        try:
            cursor.execute(
                "update product set status = 'sold' "
                "where id_product = %s and (user_id is null or user_id <> %s "
                "and starus= 'active')",
                (ad_id, buyer_id),
            )
            self.mysql.commit()
            return cursor.rowcount == 1
        finally:
            cursor.close()

    def delete_photos(self, photo_ids):
        for photo_id in photo_ids:
            if not photo_id:
                if not photo_id:
                    continue
                try:
                    self.files.delete(ObjectId(photo_id))
                except Exception:
                    pass

    def close(self):
        self.mysql.close()
        self.mongo_client.close()







