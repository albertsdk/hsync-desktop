# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpacerItem, QSplitter, QToolButton, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
        MainWindow.setMinimumSize(QSize(760, 520))
        MainWindow.setLocale(QLocale(QLocale.Italian, QLocale.Italy))
        MainWindow.setDocumentMode(False)
        self.centralWidget = QWidget(MainWindow)
        self.centralWidget.setObjectName(u"centralWidget")
        self.rootLayout = QVBoxLayout(self.centralWidget)
        self.rootLayout.setSpacing(10)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(12, 12, 12, 12)
        self.actionBarLayout = QHBoxLayout()
        self.actionBarLayout.setObjectName(u"actionBarLayout")
        self.btnStart = QPushButton(self.centralWidget)
        self.btnStart.setObjectName(u"btnStart")

        self.actionBarLayout.addWidget(self.btnStart)

        self.btnStop = QPushButton(self.centralWidget)
        self.btnStop.setObjectName(u"btnStop")
        self.btnStop.setEnabled(False)

        self.actionBarLayout.addWidget(self.btnStop)

        self.btnSync = QPushButton(self.centralWidget)
        self.btnSync.setObjectName(u"btnSync")
        self.btnSync.setEnabled(False)

        self.actionBarLayout.addWidget(self.btnSync)

        self.btnPreview = QPushButton(self.centralWidget)
        self.btnPreview.setObjectName(u"btnPreview")

        self.actionBarLayout.addWidget(self.btnPreview)

        self.actionSpacer1 = QSpacerItem(20, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.actionBarLayout.addItem(self.actionSpacer1)

        self.lblPath = QLabel(self.centralWidget)
        self.lblPath.setObjectName(u"lblPath")

        self.actionBarLayout.addWidget(self.lblPath)

        self.pathEdit = QLineEdit(self.centralWidget)
        self.pathEdit.setObjectName(u"pathEdit")

        self.actionBarLayout.addWidget(self.pathEdit)

        self.btnBrowse = QToolButton(self.centralWidget)
        self.btnBrowse.setObjectName(u"btnBrowse")

        self.actionBarLayout.addWidget(self.btnBrowse)

        self.actionSpacer2 = QSpacerItem(20, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.actionBarLayout.addItem(self.actionSpacer2)

        self.btnSettings = QPushButton(self.centralWidget)
        self.btnSettings.setObjectName(u"btnSettings")

        self.actionBarLayout.addWidget(self.btnSettings)


        self.rootLayout.addLayout(self.actionBarLayout)

        self.mainSplitter = QSplitter(self.centralWidget)
        self.mainSplitter.setObjectName(u"mainSplitter")
        self.mainSplitter.setOrientation(Qt.Vertical)
        self.mainSplitter.setChildrenCollapsible(False)
        self.filePanelPlaceholder = QWidget(self.mainSplitter)
        self.filePanelPlaceholder.setObjectName(u"filePanelPlaceholder")
        self.filePanelPlaceholder.setMinimumSize(QSize(0, 150))
        self.mainSplitter.addWidget(self.filePanelPlaceholder)
        self.logView = QPlainTextEdit(self.mainSplitter)
        self.logView.setObjectName(u"logView")
        self.logView.setMinimumSize(QSize(0, 100))
        self.logView.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.logView.setReadOnly(True)
        self.logView.setMaximumBlockCount(5000)
        self.mainSplitter.addWidget(self.logView)

        self.rootLayout.addWidget(self.mainSplitter)

        self.bottomBarLayout = QHBoxLayout()
        self.bottomBarLayout.setObjectName(u"bottomBarLayout")
        self.statusDot = QLabel(self.centralWidget)
        self.statusDot.setObjectName(u"statusDot")

        self.bottomBarLayout.addWidget(self.statusDot)

        self.statusLabel = QLabel(self.centralWidget)
        self.statusLabel.setObjectName(u"statusLabel")

        self.bottomBarLayout.addWidget(self.statusLabel)

        self.statusSpacer1 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer1)

        self.roleLabel = QLabel(self.centralWidget)
        self.roleLabel.setObjectName(u"roleLabel")

        self.bottomBarLayout.addWidget(self.roleLabel)

        self.statusSpacer2 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer2)

        self.bucketLabel = QLabel(self.centralWidget)
        self.bucketLabel.setObjectName(u"bucketLabel")

        self.bottomBarLayout.addWidget(self.bucketLabel)

        self.statusSpacer3 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer3)

        self.groupLabel = QLabel(self.centralWidget)
        self.groupLabel.setObjectName(u"groupLabel")

        self.bottomBarLayout.addWidget(self.groupLabel)

        self.statusSpacer4 = QSpacerItem(0, 0, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer4)

        self.lblPeers = QLabel(self.centralWidget)
        self.lblPeers.setObjectName(u"lblPeers")

        self.bottomBarLayout.addWidget(self.lblPeers)

        self.peersLabel = QLabel(self.centralWidget)
        self.peersLabel.setObjectName(u"peersLabel")

        self.bottomBarLayout.addWidget(self.peersLabel)

        self.statusSpacer5 = QSpacerItem(14, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer5)

        self.lblSent = QLabel(self.centralWidget)
        self.lblSent.setObjectName(u"lblSent")

        self.bottomBarLayout.addWidget(self.lblSent)

        self.sentLabel = QLabel(self.centralWidget)
        self.sentLabel.setObjectName(u"sentLabel")

        self.bottomBarLayout.addWidget(self.sentLabel)

        self.statusSpacer6 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.bottomBarLayout.addItem(self.statusSpacer6)

        self.lblRecv = QLabel(self.centralWidget)
        self.lblRecv.setObjectName(u"lblRecv")

        self.bottomBarLayout.addWidget(self.lblRecv)

        self.recvLabel = QLabel(self.centralWidget)
        self.recvLabel.setObjectName(u"recvLabel")

        self.bottomBarLayout.addWidget(self.recvLabel)


        self.rootLayout.addLayout(self.bottomBarLayout)

        MainWindow.setCentralWidget(self.centralWidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"HSYNC Desktop", None))
        self.btnStart.setText(QCoreApplication.translate("MainWindow", u"Start", None))
        self.btnStop.setText(QCoreApplication.translate("MainWindow", u"Stop", None))
        self.btnSync.setText(QCoreApplication.translate("MainWindow", u"Sync Now", None))
        self.btnPreview.setText(QCoreApplication.translate("MainWindow", u"Preview", None))
        self.lblPath.setText(QCoreApplication.translate("MainWindow", u"Path:", None))
        self.pathEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Select folder to sync...", None))
#if QT_CONFIG(tooltip)
        self.btnBrowse.setToolTip(QCoreApplication.translate("MainWindow", u"Browse for folder", None))
#endif // QT_CONFIG(tooltip)
        self.btnBrowse.setText(QCoreApplication.translate("MainWindow", u"...", None))
        self.btnSettings.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.statusDot.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: #dc3545; font-size: 14px;", None))
        self.statusDot.setText(QCoreApplication.translate("MainWindow", u"\u25cf", None))
        self.statusLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-weight: bold; font-size: 11px;", None))
        self.statusLabel.setText(QCoreApplication.translate("MainWindow", u"Disconnected", None))
        self.roleLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.roleLabel.setText(QCoreApplication.translate("MainWindow", u"\u2b21 Client", None))
        self.bucketLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-weight: bold; font-size: 11px;", None))
        self.bucketLabel.setText(QCoreApplication.translate("MainWindow", u"\u2013", None))
        self.groupLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.groupLabel.setText(QCoreApplication.translate("MainWindow", u"\u2013", None))
        self.lblPeers.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.lblPeers.setText(QCoreApplication.translate("MainWindow", u"Peers:", None))
        self.peersLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-weight: bold; font-size: 11px;", None))
        self.peersLabel.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.lblSent.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.lblSent.setText(QCoreApplication.translate("MainWindow", u"\u2191", None))
        self.sentLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.sentLabel.setText(QCoreApplication.translate("MainWindow", u"0 (0 B)", None))
        self.lblRecv.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.lblRecv.setText(QCoreApplication.translate("MainWindow", u"\u2193", None))
        self.recvLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"font-size: 11px;", None))
        self.recvLabel.setText(QCoreApplication.translate("MainWindow", u"0 (0 B)", None))
    # retranslateUi

