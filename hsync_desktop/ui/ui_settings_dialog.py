# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QSizePolicy, QSpacerItem,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget)

class Ui_SettingsDialog(object):
    def setupUi(self, SettingsDialog):
        if not SettingsDialog.objectName():
            SettingsDialog.setObjectName(u"SettingsDialog")
        SettingsDialog.resize(520, 480)
        SettingsDialog.setMinimumSize(QSize(520, 400))
        self.mainLayout = QVBoxLayout(SettingsDialog)
        self.mainLayout.setObjectName(u"mainLayout")
        self.modeLayout = QHBoxLayout()
        self.modeLayout.setObjectName(u"modeLayout")
        self.modeSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.modeLayout.addItem(self.modeSpacer)

        self.lblMode = QLabel(SettingsDialog)
        self.lblMode.setObjectName(u"lblMode")

        self.modeLayout.addWidget(self.lblMode)

        self.modeCombo = QComboBox(SettingsDialog)
        self.modeCombo.addItem("")
        self.modeCombo.addItem("")
        self.modeCombo.setObjectName(u"modeCombo")

        self.modeLayout.addWidget(self.modeCombo)


        self.mainLayout.addLayout(self.modeLayout)

        self.tabWidget = QTabWidget(SettingsDialog)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabConnection = QWidget()
        self.tabConnection.setObjectName(u"tabConnection")
        self.formConnection = QFormLayout(self.tabConnection)
        self.formConnection.setObjectName(u"formConnection")
        self.lblServerUrl = QLabel(self.tabConnection)
        self.lblServerUrl.setObjectName(u"lblServerUrl")

        self.formConnection.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblServerUrl)

        self.serverUrl = QLineEdit(self.tabConnection)
        self.serverUrl.setObjectName(u"serverUrl")

        self.formConnection.setWidget(0, QFormLayout.ItemRole.FieldRole, self.serverUrl)

        self.lblApiKey = QLabel(self.tabConnection)
        self.lblApiKey.setObjectName(u"lblApiKey")

        self.formConnection.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblApiKey)

        self.apiKey = QLineEdit(self.tabConnection)
        self.apiKey.setObjectName(u"apiKey")
        self.apiKey.setEchoMode(QLineEdit.Password)

        self.formConnection.setWidget(1, QFormLayout.ItemRole.FieldRole, self.apiKey)

        self.insecure = QCheckBox(self.tabConnection)
        self.insecure.setObjectName(u"insecure")

        self.formConnection.setWidget(2, QFormLayout.ItemRole.FieldRole, self.insecure)

        self.lblCaCert = QLabel(self.tabConnection)
        self.lblCaCert.setObjectName(u"lblCaCert")

        self.formConnection.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lblCaCert)

        self.caCert = QLineEdit(self.tabConnection)
        self.caCert.setObjectName(u"caCert")

        self.formConnection.setWidget(3, QFormLayout.ItemRole.FieldRole, self.caCert)

        self.lblHttpTimeout = QLabel(self.tabConnection)
        self.lblHttpTimeout.setObjectName(u"lblHttpTimeout")

        self.formConnection.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lblHttpTimeout)

        self.httpTimeout = QSpinBox(self.tabConnection)
        self.httpTimeout.setObjectName(u"httpTimeout")
        self.httpTimeout.setMinimum(1)
        self.httpTimeout.setMaximum(300)
        self.httpTimeout.setValue(30)

        self.formConnection.setWidget(4, QFormLayout.ItemRole.FieldRole, self.httpTimeout)

        icon = QIcon(QIcon.fromTheme(u"network-wired"))
        self.tabWidget.addTab(self.tabConnection, icon, "")
        self.tabSync = QWidget()
        self.tabSync.setObjectName(u"tabSync")
        self.formSync = QFormLayout(self.tabSync)
        self.formSync.setObjectName(u"formSync")
        self.lblBucket = QLabel(self.tabSync)
        self.lblBucket.setObjectName(u"lblBucket")

        self.formSync.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblBucket)

        self.bucket = QLineEdit(self.tabSync)
        self.bucket.setObjectName(u"bucket")

        self.formSync.setWidget(0, QFormLayout.ItemRole.FieldRole, self.bucket)

        self.continuous = QCheckBox(self.tabSync)
        self.continuous.setObjectName(u"continuous")
        self.continuous.setChecked(True)

        self.formSync.setWidget(1, QFormLayout.ItemRole.FieldRole, self.continuous)

        self.ignoreDelete = QCheckBox(self.tabSync)
        self.ignoreDelete.setObjectName(u"ignoreDelete")
        self.ignoreDelete.setChecked(True)

        self.formSync.setWidget(2, QFormLayout.ItemRole.FieldRole, self.ignoreDelete)

        self.lblResync = QLabel(self.tabSync)
        self.lblResync.setObjectName(u"lblResync")

        self.formSync.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lblResync)

        self.resync = QSpinBox(self.tabSync)
        self.resync.setObjectName(u"resync")
        self.resync.setMinimum(0)
        self.resync.setMaximum(3600)
        self.resync.setValue(0)

        self.formSync.setWidget(3, QFormLayout.ItemRole.FieldRole, self.resync)

        self.lblRetryDelay = QLabel(self.tabSync)
        self.lblRetryDelay.setObjectName(u"lblRetryDelay")

        self.formSync.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lblRetryDelay)

        self.retryDelay = QSpinBox(self.tabSync)
        self.retryDelay.setObjectName(u"retryDelay")
        self.retryDelay.setMinimum(1)
        self.retryDelay.setMaximum(60)
        self.retryDelay.setValue(5)

        self.formSync.setWidget(4, QFormLayout.ItemRole.FieldRole, self.retryDelay)

        self.lblStabilityDelay = QLabel(self.tabSync)
        self.lblStabilityDelay.setObjectName(u"lblStabilityDelay")

        self.formSync.setWidget(5, QFormLayout.ItemRole.LabelRole, self.lblStabilityDelay)

        self.stabilityDelay = QSpinBox(self.tabSync)
        self.stabilityDelay.setObjectName(u"stabilityDelay")
        self.stabilityDelay.setMinimum(0)
        self.stabilityDelay.setMaximum(60)
        self.stabilityDelay.setValue(0)

        self.formSync.setWidget(5, QFormLayout.ItemRole.FieldRole, self.stabilityDelay)

        self.lblMaxWait = QLabel(self.tabSync)
        self.lblMaxWait.setObjectName(u"lblMaxWait")

        self.formSync.setWidget(6, QFormLayout.ItemRole.LabelRole, self.lblMaxWait)

        self.maxWait = QSpinBox(self.tabSync)
        self.maxWait.setObjectName(u"maxWait")
        self.maxWait.setMinimum(10)
        self.maxWait.setMaximum(3600)
        self.maxWait.setValue(120)

        self.formSync.setWidget(6, QFormLayout.ItemRole.FieldRole, self.maxWait)

        self.lblFilterPath = QLabel(self.tabSync)
        self.lblFilterPath.setObjectName(u"lblFilterPath")

        self.formSync.setWidget(7, QFormLayout.ItemRole.LabelRole, self.lblFilterPath)

        self.filterPath = QLineEdit(self.tabSync)
        self.filterPath.setObjectName(u"filterPath")

        self.formSync.setWidget(7, QFormLayout.ItemRole.FieldRole, self.filterPath)

        self.noCompression = QCheckBox(self.tabSync)
        self.noCompression.setObjectName(u"noCompression")

        self.formSync.setWidget(8, QFormLayout.ItemRole.FieldRole, self.noCompression)

        self.dryRun = QCheckBox(self.tabSync)
        self.dryRun.setObjectName(u"dryRun")

        self.formSync.setWidget(9, QFormLayout.ItemRole.FieldRole, self.dryRun)

        icon1 = QIcon(QIcon.fromTheme(u"emblem-synchronizing"))
        self.tabWidget.addTab(self.tabSync, icon1, "")
        self.tabLan = QWidget()
        self.tabLan.setObjectName(u"tabLan")
        self.formLan = QFormLayout(self.tabLan)
        self.formLan.setObjectName(u"formLan")
        self.lanMode = QCheckBox(self.tabLan)
        self.lanMode.setObjectName(u"lanMode")

        self.formLan.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lanMode)

        self.lblLanGroup = QLabel(self.tabLan)
        self.lblLanGroup.setObjectName(u"lblLanGroup")

        self.formLan.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblLanGroup)

        self.lanGroup = QLineEdit(self.tabLan)
        self.lanGroup.setObjectName(u"lanGroup")

        self.formLan.setWidget(1, QFormLayout.ItemRole.FieldRole, self.lanGroup)

        self.lblLanKey = QLabel(self.tabLan)
        self.lblLanKey.setObjectName(u"lblLanKey")

        self.formLan.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lblLanKey)

        self.lanKey = QLineEdit(self.tabLan)
        self.lanKey.setObjectName(u"lanKey")
        self.lanKey.setEchoMode(QLineEdit.Password)

        self.formLan.setWidget(2, QFormLayout.ItemRole.FieldRole, self.lanKey)

        self.lblLanPort = QLabel(self.tabLan)
        self.lblLanPort.setObjectName(u"lblLanPort")

        self.formLan.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lblLanPort)

        self.lanPort = QSpinBox(self.tabLan)
        self.lanPort.setObjectName(u"lanPort")
        self.lanPort.setMinimum(0)
        self.lanPort.setMaximum(65535)
        self.lanPort.setValue(0)

        self.formLan.setWidget(3, QFormLayout.ItemRole.FieldRole, self.lanPort)

        self.lblDiscoveryTimeout = QLabel(self.tabLan)
        self.lblDiscoveryTimeout.setObjectName(u"lblDiscoveryTimeout")

        self.formLan.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lblDiscoveryTimeout)

        self.discoveryTimeout = QSpinBox(self.tabLan)
        self.discoveryTimeout.setObjectName(u"discoveryTimeout")
        self.discoveryTimeout.setMinimum(1)
        self.discoveryTimeout.setMaximum(120)
        self.discoveryTimeout.setValue(10)

        self.formLan.setWidget(4, QFormLayout.ItemRole.FieldRole, self.discoveryTimeout)

        self.lanHttps = QCheckBox(self.tabLan)
        self.lanHttps.setObjectName(u"lanHttps")
        self.lanHttps.setChecked(True)

        self.formLan.setWidget(5, QFormLayout.ItemRole.FieldRole, self.lanHttps)

        self.lanPersistent = QCheckBox(self.tabLan)
        self.lanPersistent.setObjectName(u"lanPersistent")
        self.lanPersistent.setChecked(True)

        self.formLan.setWidget(6, QFormLayout.ItemRole.FieldRole, self.lanPersistent)

        icon2 = QIcon(QIcon.fromTheme(u"network-workgroup"))
        self.tabWidget.addTab(self.tabLan, icon2, "")
        self.tabLog = QWidget()
        self.tabLog.setObjectName(u"tabLog")
        self.formLog = QFormLayout(self.tabLog)
        self.formLog.setObjectName(u"formLog")
        self.verbose = QCheckBox(self.tabLog)
        self.verbose.setObjectName(u"verbose")

        self.formLog.setWidget(0, QFormLayout.ItemRole.FieldRole, self.verbose)

        self.quiet = QCheckBox(self.tabLog)
        self.quiet.setObjectName(u"quiet")

        self.formLog.setWidget(1, QFormLayout.ItemRole.FieldRole, self.quiet)

        self.lblLogfile = QLabel(self.tabLog)
        self.lblLogfile.setObjectName(u"lblLogfile")

        self.formLog.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lblLogfile)

        self.logfile = QLineEdit(self.tabLog)
        self.logfile.setObjectName(u"logfile")

        self.formLog.setWidget(2, QFormLayout.ItemRole.FieldRole, self.logfile)

        icon3 = QIcon(QIcon.fromTheme(u"utilities-log-viewer"))
        self.tabWidget.addTab(self.tabLog, icon3, "")
        self.tabAppearance = QWidget()
        self.tabAppearance.setObjectName(u"tabAppearance")
        self.formAppearance = QFormLayout(self.tabAppearance)
        self.formAppearance.setObjectName(u"formAppearance")
        self.lblTheme = QLabel(self.tabAppearance)
        self.lblTheme.setObjectName(u"lblTheme")

        self.formAppearance.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblTheme)

        self.themeCombo = QComboBox(self.tabAppearance)
        self.themeCombo.addItem("")
        self.themeCombo.addItem("")
        self.themeCombo.setObjectName(u"themeCombo")

        self.formAppearance.setWidget(0, QFormLayout.ItemRole.FieldRole, self.themeCombo)

        self.lblLanguage = QLabel(self.tabAppearance)
        self.lblLanguage.setObjectName(u"lblLanguage")

        self.formAppearance.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblLanguage)

        self.langCombo = QComboBox(self.tabAppearance)
        self.langCombo.addItem("")
        self.langCombo.addItem("")
        self.langCombo.addItem("")
        self.langCombo.addItem("")
        self.langCombo.addItem("")
        self.langCombo.setObjectName(u"langCombo")

        self.formAppearance.setWidget(1, QFormLayout.ItemRole.FieldRole, self.langCombo)

        self.notificationsEnabled = QCheckBox(self.tabAppearance)
        self.notificationsEnabled.setObjectName(u"notificationsEnabled")
        self.notificationsEnabled.setChecked(True)

        self.formAppearance.setWidget(2, QFormLayout.ItemRole.FieldRole, self.notificationsEnabled)

        self.tooltipsEnabled = QCheckBox(self.tabAppearance)
        self.tooltipsEnabled.setObjectName(u"tooltipsEnabled")
        self.tooltipsEnabled.setChecked(True)

        self.formAppearance.setWidget(3, QFormLayout.ItemRole.FieldRole, self.tooltipsEnabled)

        icon4 = QIcon(QIcon.fromTheme(u"preferences-desktop-theme"))
        self.tabWidget.addTab(self.tabAppearance, icon4, "")

        self.mainLayout.addWidget(self.tabWidget)

        self.buttonBox = QDialogButtonBox(SettingsDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.mainLayout.addWidget(self.buttonBox)


        self.retranslateUi(SettingsDialog)
        self.buttonBox.accepted.connect(SettingsDialog.accept)
        self.buttonBox.rejected.connect(SettingsDialog.reject)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(SettingsDialog)
    # setupUi

    def retranslateUi(self, SettingsDialog):
        SettingsDialog.setWindowTitle(QCoreApplication.translate("SettingsDialog", u"Settings", None))
        self.lblMode.setText(QCoreApplication.translate("SettingsDialog", u"Mode:", None))
        self.modeCombo.setItemText(0, QCoreApplication.translate("SettingsDialog", u"Default", None))
        self.modeCombo.setItemText(1, QCoreApplication.translate("SettingsDialog", u"Advanced", None))

        self.lblServerUrl.setText(QCoreApplication.translate("SettingsDialog", u"Server URL:", None))
        self.serverUrl.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"https://server.example.com", None))
        self.lblApiKey.setText(QCoreApplication.translate("SettingsDialog", u"API Key:", None))
        self.apiKey.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"(optional)", None))
        self.insecure.setText(QCoreApplication.translate("SettingsDialog", u"Skip SSL verification", None))
        self.lblCaCert.setText(QCoreApplication.translate("SettingsDialog", u"CA Certificate:", None))
        self.caCert.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"/path/to/ca.pem", None))
        self.lblHttpTimeout.setText(QCoreApplication.translate("SettingsDialog", u"HTTP Timeout:", None))
        self.httpTimeout.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabConnection), QCoreApplication.translate("SettingsDialog", u"Connection", None))
        self.lblBucket.setText(QCoreApplication.translate("SettingsDialog", u"Bucket:", None))
        self.bucket.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"my-bucket", None))
        self.continuous.setText(QCoreApplication.translate("SettingsDialog", u"Watch for changes", None))
        self.ignoreDelete.setText(QCoreApplication.translate("SettingsDialog", u"Ignore deletions", None))
        self.lblResync.setText(QCoreApplication.translate("SettingsDialog", u"Resync interval:", None))
        self.resync.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.resync.setSpecialValueText(QCoreApplication.translate("SettingsDialog", u"Disabled", None))
        self.lblRetryDelay.setText(QCoreApplication.translate("SettingsDialog", u"Retry delay:", None))
        self.retryDelay.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.lblStabilityDelay.setText(QCoreApplication.translate("SettingsDialog", u"Stability delay:", None))
        self.stabilityDelay.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.stabilityDelay.setSpecialValueText(QCoreApplication.translate("SettingsDialog", u"Auto", None))
        self.lblMaxWait.setText(QCoreApplication.translate("SettingsDialog", u"Max wait:", None))
        self.maxWait.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.lblFilterPath.setText(QCoreApplication.translate("SettingsDialog", u"Filter path:", None))
        self.filterPath.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"(optional)", None))
        self.noCompression.setText(QCoreApplication.translate("SettingsDialog", u"Disable compression", None))
        self.dryRun.setText(QCoreApplication.translate("SettingsDialog", u"Dry run (preview only)", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabSync), QCoreApplication.translate("SettingsDialog", u"Sync", None))
        self.lanMode.setText(QCoreApplication.translate("SettingsDialog", u"Enable LAN mode", None))
        self.lblLanGroup.setText(QCoreApplication.translate("SettingsDialog", u"LAN Group:", None))
        self.lanGroup.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"my-group", None))
        self.lblLanKey.setText(QCoreApplication.translate("SettingsDialog", u"LAN Key:", None))
        self.lanKey.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"(optional)", None))
        self.lblLanPort.setText(QCoreApplication.translate("SettingsDialog", u"LAN Port:", None))
        self.lanPort.setSpecialValueText(QCoreApplication.translate("SettingsDialog", u"Auto", None))
        self.lblDiscoveryTimeout.setText(QCoreApplication.translate("SettingsDialog", u"Discovery timeout:", None))
        self.discoveryTimeout.setSuffix(QCoreApplication.translate("SettingsDialog", u" s", None))
        self.lanHttps.setText(QCoreApplication.translate("SettingsDialog", u"Use HTTPS", None))
        self.lanPersistent.setText(QCoreApplication.translate("SettingsDialog", u"Persistent mode", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabLan), QCoreApplication.translate("SettingsDialog", u"LAN Mode", None))
        self.verbose.setText(QCoreApplication.translate("SettingsDialog", u"Verbose output", None))
        self.quiet.setText(QCoreApplication.translate("SettingsDialog", u"Quiet mode", None))
        self.lblLogfile.setText(QCoreApplication.translate("SettingsDialog", u"Log file:", None))
        self.logfile.setPlaceholderText(QCoreApplication.translate("SettingsDialog", u"/path/to/logfile.log", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabLog), QCoreApplication.translate("SettingsDialog", u"Log", None))
        self.lblTheme.setText(QCoreApplication.translate("SettingsDialog", u"Theme:", None))
        self.themeCombo.setItemText(0, QCoreApplication.translate("SettingsDialog", u"Light", None))
        self.themeCombo.setItemText(1, QCoreApplication.translate("SettingsDialog", u"Dark", None))

        self.lblLanguage.setText(QCoreApplication.translate("SettingsDialog", u"Language:", None))
        self.langCombo.setItemText(0, QCoreApplication.translate("SettingsDialog", u"English", None))
        self.langCombo.setItemText(1, QCoreApplication.translate("SettingsDialog", u"Italiano", None))
        self.langCombo.setItemText(2, QCoreApplication.translate("SettingsDialog", u"Deutsch", None))
        self.langCombo.setItemText(3, QCoreApplication.translate("SettingsDialog", u"Fran\u00e7ais", None))
        self.langCombo.setItemText(4, QCoreApplication.translate("SettingsDialog", u"Espa\u00f1ol", None))

        self.notificationsEnabled.setText(QCoreApplication.translate("SettingsDialog", u"Enable notifications", None))
        self.tooltipsEnabled.setText(QCoreApplication.translate("SettingsDialog", u"Show tooltips", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabAppearance), QCoreApplication.translate("SettingsDialog", u"Appearance", None))
    # retranslateUi

