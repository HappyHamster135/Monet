// Presentation only: every button uses the existing, permission-aware action.
    m_ui->toolBar->setMovable(false);
    m_ui->toolBar->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
    for (auto* action : m_ui->toolBar->actions()) {
        m_ui->toolBar->removeAction(action);
    }
    auto* monetName = new QLabel(tr("Passwords"), m_ui->toolBar);
    monetName->setObjectName("monetPasswordsName");
    monetName->setContentsMargins(12, 4, 18, 4);
    auto monetFont = monetName->font();
    monetFont.setFamily("Fraunces 72pt SuperSoft");
    monetFont.setPointSize(monetFont.pointSize() + 6);
    monetName->setFont(monetFont);
    m_ui->toolBar->addWidget(monetName);
    m_ui->toolBar->addAction(m_searchWidgetAction);
    m_ui->actionEntryNew->setText(tr("Add login"));
    m_ui->actionEntryEdit->setText(tr("Edit login"));
    m_ui->actionEntryDelete->setText(tr("Delete login"));
    m_ui->actionEntryCopyUsername->setText(tr("Copy username"));
    m_ui->actionEntryCopyPassword->setText(tr("Copy password"));
    m_ui->actionLockDatabaseToolbar->setText(tr("Lock vault"));
    m_ui->toolBar->addAction(m_ui->actionEntryNew);
    for (auto* action : {m_ui->actionEntryEdit, m_ui->actionEntryCopyPassword,
                         m_ui->actionEntryDelete, m_ui->actionLockDatabaseToolbar}) {
        m_ui->toolBar->addAction(action);
        auto* button = qobject_cast<QToolButton*>(m_ui->toolBar->widgetForAction(action));
        if (button) {
            button->setToolButtonStyle(Qt::ToolButtonIconOnly);
        }
    }
    auto* monetMore = new QToolButton(m_ui->toolBar);
    monetMore->setObjectName("monetPasswordsMore");
    monetMore->setText(tr("More"));
    monetMore->setAccessibleName(tr("More password actions"));
    monetMore->setPopupMode(QToolButton::InstantPopup);
    auto* monetMenu = new QMenu(monetMore);
    for (auto* action : m_ui->menubar->actions()) {
        monetMenu->addAction(action);
    }
    monetMore->setMenu(monetMenu);
    m_ui->toolBar->addWidget(monetMore);
    auto* monetPreview = new QLabel(tr("Monet preview · Use test logins · Powered by KeePassXC"), this);
    monetPreview->setObjectName("monetPasswordsPreview");
    monetPreview->setContentsMargins(8, 0, 8, 0);
    statusBar()->addWidget(monetPreview);
