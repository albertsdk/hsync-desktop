# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'file_panel.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QSpacerItem, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_FilePanel(object):
    def setupUi(self, FilePanel):
        if not FilePanel.objectName():
            FilePanel.setObjectName(u"FilePanel")
        FilePanel.resize(700, 300)
        FilePanel.setMinimumSize(QSize(400, 150))
        self.mainLayout = QHBoxLayout(FilePanel)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(FilePanel)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(True)
        self.transferTable = QTableWidget(self.splitter)
        if (self.transferTable.columnCount() < 7):
            self.transferTable.setColumnCount(7)
        __qtablewidgetitem = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.transferTable.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        self.transferTable.setObjectName(u"transferTable")
        self.transferTable.setAlternatingRowColors(True)
        self.transferTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.transferTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.transferTable.setSortingEnabled(True)
        self.transferTable.setShowGrid(False)
        self.transferTable.setColumnCount(7)
        self.splitter.addWidget(self.transferTable)
        self.detailPanel = QFrame(self.splitter)
        self.detailPanel.setObjectName(u"detailPanel")
        self.detailPanel.setMinimumSize(QSize(220, 0))
        self.detailPanel.setFrameShape(QFrame.StyledPanel)
        self.detailPanel.setFrameShadow(QFrame.Sunken)
        self.detailLayout = QVBoxLayout(self.detailPanel)
        self.detailLayout.setObjectName(u"detailLayout")
        self.lblDetailTitle = QLabel(self.detailPanel)
        self.lblDetailTitle.setObjectName(u"lblDetailTitle")
        font = QFont()
        font.setBold(True)
        self.lblDetailTitle.setFont(font)

        self.detailLayout.addWidget(self.lblDetailTitle)

        self.detailForm = QFormLayout()
        self.detailForm.setObjectName(u"detailForm")
        self.lblFilepath = QLabel(self.detailPanel)
        self.lblFilepath.setObjectName(u"lblFilepath")

        self.detailForm.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblFilepath)

        self.valFilepath = QLabel(self.detailPanel)
        self.valFilepath.setObjectName(u"valFilepath")
        self.valFilepath.setWordWrap(True)

        self.detailForm.setWidget(0, QFormLayout.ItemRole.FieldRole, self.valFilepath)

        self.lblFilename = QLabel(self.detailPanel)
        self.lblFilename.setObjectName(u"lblFilename")

        self.detailForm.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblFilename)

        self.valFilename = QLabel(self.detailPanel)
        self.valFilename.setObjectName(u"valFilename")
        self.valFilename.setWordWrap(True)

        self.detailForm.setWidget(1, QFormLayout.ItemRole.FieldRole, self.valFilename)

        self.lblSize = QLabel(self.detailPanel)
        self.lblSize.setObjectName(u"lblSize")

        self.detailForm.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lblSize)

        self.valSize = QLabel(self.detailPanel)
        self.valSize.setObjectName(u"valSize")

        self.detailForm.setWidget(2, QFormLayout.ItemRole.FieldRole, self.valSize)

        self.lblDirection = QLabel(self.detailPanel)
        self.lblDirection.setObjectName(u"lblDirection")

        self.detailForm.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lblDirection)

        self.valDirection = QLabel(self.detailPanel)
        self.valDirection.setObjectName(u"valDirection")

        self.detailForm.setWidget(3, QFormLayout.ItemRole.FieldRole, self.valDirection)

        self.lblStatus = QLabel(self.detailPanel)
        self.lblStatus.setObjectName(u"lblStatus")

        self.detailForm.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lblStatus)

        self.valStatus = QLabel(self.detailPanel)
        self.valStatus.setObjectName(u"valStatus")

        self.detailForm.setWidget(4, QFormLayout.ItemRole.FieldRole, self.valStatus)

        self.lblClientCid = QLabel(self.detailPanel)
        self.lblClientCid.setObjectName(u"lblClientCid")

        self.detailForm.setWidget(5, QFormLayout.ItemRole.LabelRole, self.lblClientCid)

        self.valClientCid = QLabel(self.detailPanel)
        self.valClientCid.setObjectName(u"valClientCid")

        self.detailForm.setWidget(5, QFormLayout.ItemRole.FieldRole, self.valClientCid)

        self.lblClientIp = QLabel(self.detailPanel)
        self.lblClientIp.setObjectName(u"lblClientIp")

        self.detailForm.setWidget(6, QFormLayout.ItemRole.LabelRole, self.lblClientIp)

        self.valClientIp = QLabel(self.detailPanel)
        self.valClientIp.setObjectName(u"valClientIp")

        self.detailForm.setWidget(6, QFormLayout.ItemRole.FieldRole, self.valClientIp)


        self.detailLayout.addLayout(self.detailForm)

        self.detailSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.detailLayout.addItem(self.detailSpacer)

        self.splitter.addWidget(self.detailPanel)

        self.mainLayout.addWidget(self.splitter)


        self.retranslateUi(FilePanel)

        QMetaObject.connectSlotsByName(FilePanel)
    # setupUi

    def retranslateUi(self, FilePanel):
        ___qtablewidgetitem = self.transferTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("FilePanel", u"Dir", None));
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem.setToolTip(QCoreApplication.translate("FilePanel", u"Direction (download/upload)", None));
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem1 = self.transferTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("FilePanel", u"Path", None));
        ___qtablewidgetitem2 = self.transferTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("FilePanel", u"Name", None));
        ___qtablewidgetitem3 = self.transferTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("FilePanel", u"Size", None));
        ___qtablewidgetitem4 = self.transferTable.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("FilePanel", u"Remaining", None));
        ___qtablewidgetitem5 = self.transferTable.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("FilePanel", u"ETA", None));
        ___qtablewidgetitem6 = self.transferTable.horizontalHeaderItem(6)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("FilePanel", u"Status", None));
        self.lblDetailTitle.setText(QCoreApplication.translate("FilePanel", u"File Details", None))
        self.lblFilepath.setText(QCoreApplication.translate("FilePanel", u"Path:", None))
        self.valFilepath.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblFilename.setText(QCoreApplication.translate("FilePanel", u"Name:", None))
        self.valFilename.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblSize.setText(QCoreApplication.translate("FilePanel", u"Size:", None))
        self.valSize.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblDirection.setText(QCoreApplication.translate("FilePanel", u"Direction:", None))
        self.valDirection.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblStatus.setText(QCoreApplication.translate("FilePanel", u"Status:", None))
        self.valStatus.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblClientCid.setText(QCoreApplication.translate("FilePanel", u"Client CID:", None))
        self.valClientCid.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        self.lblClientIp.setText(QCoreApplication.translate("FilePanel", u"Client IP:", None))
        self.valClientIp.setText(QCoreApplication.translate("FilePanel", u"\u2013", None))
        pass
    # retranslateUi

