# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'splash_screen.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_SplashScreen(object):
    def setupUi(self, SplashScreen):
        if not SplashScreen.objectName():
            SplashScreen.setObjectName(u"SplashScreen")
        SplashScreen.resize(380, 200)
        SplashScreen.setMinimumSize(QSize(380, 200))
        SplashScreen.setMaximumSize(QSize(380, 200))
        self.mainLayout = QVBoxLayout(SplashScreen)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(30, 30, 30, 30)
        self.lblAppName = QLabel(SplashScreen)
        self.lblAppName.setObjectName(u"lblAppName")
        self.lblAppName.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        self.lblAppName.setFont(font)

        self.mainLayout.addWidget(self.lblAppName)

        self.spacer1 = QSpacerItem(20, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.mainLayout.addItem(self.spacer1)

        self.lblWelcome = QLabel(SplashScreen)
        self.lblWelcome.setObjectName(u"lblWelcome")
        self.lblWelcome.setAlignment(Qt.AlignCenter)
        font1 = QFont()
        font1.setPointSize(11)
        self.lblWelcome.setFont(font1)

        self.mainLayout.addWidget(self.lblWelcome)

        self.spacer2 = QSpacerItem(20, 12, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.mainLayout.addItem(self.spacer2)

        self.lblVersion = QLabel(SplashScreen)
        self.lblVersion.setObjectName(u"lblVersion")
        self.lblVersion.setAlignment(Qt.AlignCenter)

        self.mainLayout.addWidget(self.lblVersion)


        self.retranslateUi(SplashScreen)

        QMetaObject.connectSlotsByName(SplashScreen)
    # setupUi

    def retranslateUi(self, SplashScreen):
        SplashScreen.setWindowTitle(QCoreApplication.translate("SplashScreen", u"HSYNC Desktop", None))
        SplashScreen.setStyleSheet(QCoreApplication.translate("SplashScreen", u"QWidget#SplashScreen {\n"
"  background-color: palette(window);\n"
"  border: 1px solid palette(mid);\n"
"  border-radius: 10px;\n"
"}", None))
        self.lblAppName.setText(QCoreApplication.translate("SplashScreen", u"HSYNC Desktop", None))
        self.lblWelcome.setText(QCoreApplication.translate("SplashScreen", u"Welcome to HSYNC", None))
        self.lblVersion.setText(QCoreApplication.translate("SplashScreen", u"Version 0.1.0", None))
        self.lblVersion.setStyleSheet(QCoreApplication.translate("SplashScreen", u"color: gray;", None))
    # retranslateUi

