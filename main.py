import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QApplication, QDialog, QGridLayout, QLabel, QPushButton, QMainWindow, QMessageBox, QFileDialog)

from add_window import Ui_AddAdWindow
from basket_window import Ui_BasketWindow
from main_window import Ui_MainWindow
from database import Database
from login_dialog import Ui_LoginDialog
from personal_cabinet import Ui_PersonalCabinet
from product_card import Ui_ProductCard
from register_dialog import Ui_RegisterDialog

class AddWindow(QDialog):
    def __init__(self, storage, user, parent=None):
        super().__init__(parent)
        self.ui = Ui_AddAdWindow()
        self.ui.setupUi(self)
        self.storage = storage
        self.user = user
        self.photos = []

    def choose_photos(self):
        self.photos, _ = QFileDialog.getOpenFileNames(
            self,"Выберите фотографии","","Изображения (*.png *.jpg *.jpeg *.webp)",)
        self.ui.photosLabel.setText(f"Выбрано фотографий: {len(self.photos)}")

    def publish(self):
        title = self.ui.titleLabel.text().strip()
        description = self.ui.descriptionEdit.toPlainText().strip()

        try:
            price = float(self.ui.priceEdit.text().replace(",", ".")or 0)
            if not title or not description or price < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                 self,
                "Проверьте данные",
                "Укажите название, описание и корректную цену.",
            )
            return
        try:
            self.storage.add(self.user["id"], title, description, price, self.ui.categoryCombo.currentText(), self.photos,)
            self.accept()
        except Exception as error:
            QMessageBox.critical(self, "Ошиька публикации", str(error))

class ProductWindow(QDialog):
    def __init__(self, storage,ad, on_add_to_cart=None, parent=None):
        super().__init__(parent)
        self.ui = Ui_ProductCard()
        self.ui.setupUi(self)
        self.setWindowTitle(ad["title"])
        self.ui.priceLabel.setText(f"{ad['price']} ₽")
        self.ui.categoryLabel.setText(f"Категория: {ad['category']}")
        self.ui.sellerLabel.setText(f"Продавец: {ad['seller']}")
        self.ui.descriptionLabel.setText(ad["description"])

        self.show_photos(storage, ad.get("photos_ids", ""))
        if on_add_to_cart is None:
            self.ui.addToCartButton.hide()
        else:
            self.ui.addToCartButton.clicked.connect(
                lambda: on_add_to_cart(ad)
            )

    def show_photos(self, storage, photo_ids):
        ids = filter(None, (photo_ids or "").split(","))
        for photo_id in ids:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(storage.get_photo(photo_id))
                lable = QLabel()
                lable.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lable.setPixmap(pixmap.scaled(
                    360,
                    260,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                self.ui.photosLayout.addWidget(lable)
            except Exception:
                continue

        if not self.ui.photosLayout.count():
            lable = QLabel("Фотографии не добавлены")
            lable.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ui.photosLayout.addWidget(lable)

class BasketWindow(QDialog):
    def __init__(self, storage, basket, buyer, on_ordered, parent=None):
        super().__init__(parent)
        self.ui = Ui_BasketWindow()
        self.ui.setupUi(self)
        self.storage = storage
        self.basket = basket
        self.buyer = buyer
        self.on_ordered = on_ordered
        self.ui.orderButton.clicked.connect(self.place_order)
        self.refresh()

    def refresh(self):
        self.ui.basketList.clear()
        total = 0
        for ad in self.basket.values():
            self.ui.basketList.addItem(f"{ad['title']} — {ad['price']} ₽")
            total += float(ad["price"])
        self.ui.totalLabel.setText(f"Итого: {total:.2f} ₽")

    def place_order(self):
        if not self.basket:
            QMessageBox.information(self, "Корзина пуста", "Добавьте объявление из каталога.")
            return

        answer = QMessageBox.question(
            self,
            "Подтвердить заказ",
            "Заказать все объявления из корзины?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        ordered = 0
        unavailable = 0
        for ad_id in list(self.basket):
            if self.storage.order_ad(ad_id, self.buyer["id"]):
                ordered += 1
            else:
                unavailable += 1
            self.basket.pop(ad_id, None)

        self.refresh()
        self.on_ordered()
        message = f"Заказано объявлений: {ordered}. Они сняты с доски."
        if unavailable:
            message += f"\nНедоступных объявлений: {unavailable}."
        QMessageBox.information(self, "Заказ обработан", message)
        if not self.basket:
            self.accept()

class PersonalCabinetWindow(QDialog):
    def __init__(self, storage, user, parent=None):
        super().__init__(parent)
        self.ui = Ui_PersonalCabinet()
        self.ui.setupUi(self)
        self.storage = storage
        self.user = user
        self.setWindowTitle(f"Личный кабинет — {user['name']}")
        self.ui.profileLabel.setText(
            f"Пользователь: {user['name']} · {user['email']}"
        )
        self.ui.adsList.itemDoubleClicked.connect(self.open_ad)
        self.ui.deleteAdButton.clicked.connect(self.delete_selected_ad)
        self.refresh()

    def refresh(self):
        self.ui.adsList.clear()
        try:
            self.ads = self.storage.ads(self.user["id"])
            for ad in self.ads:
                self.ui.adsList.addItem(f"{ad['title']} — {ad['price']} ₽")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка загрузки кабинета", str(error))

    def open_ad(self, item):
        ad = self.ads[self.ui.adsList.row(item)]
        ProductWindow(self.storage, ad, parent=self).exec()

    def delete_selected_ad(self):
        row = self.ui.adsList.currentRow()
        if row < 0:
            QMessageBox.information(self, "Ничего не выбрано", "Выберите объявление.")
            return

        ad = self.ads[row]
        answer = QMessageBox.question(
            self,
            "Удалить объявление?",
            f"Удалить «{ad['title']}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.storage.delete_ad(ad["id"], self.user["id"])
            self.refresh()
        except Exception as error:
            QMessageBox.critical(self, "Не удалось удалить объявление", str(error))

class MainWindow(QMainWindow):
    def __init__(self, storage):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.storage = storage
        self.user = None
        self.cart = {}

        self.ui.accountButton.clicked.connect(self.account_action)
        self.ui.addAdButton.clicked.connect(self.add_ad)

    def account_action(self):
        if self.user:
            PersonalCabinetWindow(self.storage, self.user, self).exec()
        else:
            self.login()

    def login(self):
        dialog = QDialog(self)
        ui = Ui_LoginDialog()
        ui.setupUi(dialog)
        ui.loginButton.clicked.connect(lambda: self.login_user(dialog, ui))
        ui.openRegisterButton.clicked.connect(lambda: self.open_registration(dialog))
        dialog.exec()

    def open_registration(self, login_dialog):
        login_dialog.accept()
        self.register()

    def login_user(self, dialog, ui):
        user = self.storage.login(ui.loginEdit.text().strip(), ui.passwordEdit.text())
        if not user:
            QMessageBox.warning(dialog, "Вход не выполнен", "Проверьте логин или пароль")
            return
        self.set_user(user)
        dialog.accept()

    def register(self):
        dialog = QDialog(self)
        ui = Ui_RegisterDialog()
        ui.setupUi(dialog)
        ui.registerButton.clicked.connect(lambda: self.register_user(dialog, ui))
        dialog.exec()

    def register_user(self, dialog, ui):
        login = ui.loginEdit.text().strip()
        email = ui.emailEdit.text().strip()
        password = ui.passwordEdit.text()
        if not login or "@" not in email or len(password) < 6:
            QMessageBox.warning(dialog, "Проверьте данные", "Введите логи, поччту и пароль не короче 6 символов ")
            return
        try:
            user_id = self.storage.register(login, email, password)
            self.set_user({"id": user_id, "name": login, "email": email})
            dialog.accept()
        except Exception as error:
            QMessageBox.critical(dialog, "Ошибка ренистрации", str(error))

    def set_user(self, user):
        self.user = user
        self.ui.accountButton.setText(user["name"])

    def add_ad(self):
        if not self.user:
            QMessageBox.information(self, "Нужен аккаунт", "Сначччала войдите в аккаунт")
            self.login()
            if not self.user:
                return

            if not self.cart:
                QMessageBox.information(self, "Корзина пуста", "Добавьте товар")
                return
            if not self.user:
                self.login()
                if not self.user:
                    return

            BasketWindow(self.storage, self.cart, self.user, self).exec()

def main():
    app = QApplication(sys.argv)
    try:
        storage = Database()
    except Exception as error:
        QMessageBox.critical(None, "Ошибка подклюения","Проверьте настройки")
        return 1

    window = MainWindow(storage)
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())




