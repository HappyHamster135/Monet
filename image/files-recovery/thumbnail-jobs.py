"""Expose native preview work through Files' existing progress and Stop controls."""
from pathlib import Path


def apply(root):
    root = Path(root)

    def patch(name, before, after):
        path = root / name
        text = path.read_text()
        if text.count(before) != 1:
            raise SystemExit('Dolphin thumbnail source changed: ' + name)
        path.write_text(text.replace(before, after))

    patch('src/kitemviews/kfileitemmodel.h', '    void cancelDirectoryLoading();', '''    void cancelDirectoryLoading();

    bool previewsLoading() const { return property("_monetPreviewsLoading").toBool(); }
    void cancelPreviews() { Q_EMIT previewCancellationRequested(); }
''')
    patch('src/kitemviews/kfileitemmodel.h', 'Q_SIGNALS:', '''Q_SIGNALS:
    void previewsLoadingChanged(bool loading);
    void previewCancellationRequested();
''')
    patch('src/kitemviews/kfileitemmodel.h', '    friend class KFileItemModelRolesUpdater;', '''    void setPreviewsLoading(bool loading)
    {
        if (previewsLoading() == loading) return;
        setProperty("_monetPreviewsLoading", loading);
        Q_EMIT previewsLoadingChanged(loading);
    }

    friend class KFileItemModelRolesUpdater;''')

    patch('src/kitemviews/kfileitemmodelrolesupdater.h', '    void killPreviewJob();', '''    void killPreviewJob();
    void killPreviewJob(bool notifyModel);
    void cancelPreviews();
    bool previewsCanceled() const { return property("_monetPreviewsCanceled").toBool(); }''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '    Q_ASSERT(model);', '''    Q_ASSERT(model);
    m_model->setPreviewsLoading(false);
    connect(m_model, &KFileItemModel::previewCancellationRequested, this, &KFileItemModelRolesUpdater::cancelPreviews);
    connect(m_model, &KFileItemModel::directoryLoadingStarted, this, [this] {
        // A fresh listing (including Refresh) resumes work without changing
        // the user's persistent per-folder preview setting.
        setProperty("_monetPreviewsCanceled", false);
        m_finishedItems.clear();
    });
    connect(m_model, &KFileItemModel::directoryLoadingCompleted, this, &KFileItemModelRolesUpdater::startUpdating);''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''KFileItemModelRolesUpdater::~KFileItemModelRolesUpdater()
{
    killPreviewJob();
}''', '''KFileItemModelRolesUpdater::~KFileItemModelRolesUpdater()
{
    // The model may already have been destroyed during view teardown.
    killPreviewJob(false);
}

void KFileItemModelRolesUpdater::cancelPreviews()
{
    setProperty("_monetPreviewsCanceled", true);
    killPreviewJob();
    killHoverSequencePreviewJob();
    m_pendingPreviewItems.clear();
    if (m_state == PreviewJobRunning) m_state = Idle;
}''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '    m_previewShown = show;', '''    m_previewShown = show;
    if (show) setProperty("_monetPreviewsCanceled", false);''')
    # Keep metadata resolution available after Stop; only expensive previews
    # are paused, and completed pixmaps remain in the model/cache.
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''    if (m_previewShown) {
        m_pendingPreviewItems.clear();''', '''    if (m_previewShown && !previewsCanceled()) {
        m_pendingPreviewItems.clear();''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''    if (m_previewShown) {
        for (int index : std::as_const(visibleChangedIndexes))''', '''    if (m_previewShown && !previewsCanceled()) {
        for (int index : std::as_const(visibleChangedIndexes))''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''void KFileItemModelRolesUpdater::startPreviewJob()
{
    m_state = PreviewJobRunning;''', '''void KFileItemModelRolesUpdater::startPreviewJob()
{
    if (previewsCanceled()) {
        m_pendingPreviewItems.clear();
        m_state = Idle;
        m_model->setPreviewsLoading(false);
        return;
    }
    m_state = PreviewJobRunning;''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '    m_previewJob = job;', '''    m_previewJob = job;
    m_model->setPreviewsLoading(true);''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''void KFileItemModelRolesUpdater::slotPreviewJobFinished()
{
    m_previewJob = nullptr;

    if (m_state != PreviewJobRunning) {
        return;
    }''', '''void KFileItemModelRolesUpdater::slotPreviewJobFinished()
{
    m_previewJob = nullptr;

    if (m_state != PreviewJobRunning) {
        m_model->setPreviewsLoading(false);
        return;
    }''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''        if (!m_changedItems.isEmpty()) {
            updateChangedItems();
        }
    }
}

void KFileItemModelRolesUpdater::slotHoverSequenceGotPreview''', '''        if (!m_changedItems.isEmpty()) {
            updateChangedItems();
        }
    }
    if (!m_previewJob && m_pendingPreviewItems.isEmpty()) m_model->setPreviewsLoading(false);
}

void KFileItemModelRolesUpdater::slotHoverSequenceGotPreview''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''void KFileItemModelRolesUpdater::loadNextHoverSequencePreview()
{''', '''void KFileItemModelRolesUpdater::loadNextHoverSequencePreview()
{
    if (previewsCanceled()) return;''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''void KFileItemModelRolesUpdater::killPreviewJob()
{''', '''void KFileItemModelRolesUpdater::killPreviewJob()
{
    killPreviewJob(true);
}

void KFileItemModelRolesUpdater::killPreviewJob(bool notifyModel)
{''')
    patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', '''        m_pendingPreviewItems.clear();
    }
}

QList<int> KFileItemModelRolesUpdater::indexesToResolve() const''', '''        m_pendingPreviewItems.clear();
    }
    if (notifyModel) m_model->setPreviewsLoading(false);
}

QList<int> KFileItemModelRolesUpdater::indexesToResolve() const''')

    patch('src/views/dolphinview.h', '    bool previewsShown() const;', '''    bool previewsShown() const;
    bool previewsLoading() const;
    bool directoryLoading() const;
    bool isLoading() const;''')
    patch('src/views/dolphinview.h', 'Q_SIGNALS:', '''Q_SIGNALS:
    void previewsLoadingChanged(bool loading);
''')
    patch('src/views/dolphinview.cpp', '''    connect(m_model, &KFileItemModel::directoryLoadingStarted, this, &DolphinView::slotDirectoryLoadingStarted);''', '''    connect(m_model, &KFileItemModel::previewsLoadingChanged, this, &DolphinView::previewsLoadingChanged);
    connect(m_model, &KFileItemModel::directoryLoadingStarted, this, &DolphinView::slotDirectoryLoadingStarted);''')
    patch('src/views/dolphinview.cpp', '''void DolphinView::stopLoading()
{
    m_model->cancelDirectoryLoading();
}''', '''bool DolphinView::previewsLoading() const
{
    return m_model->previewsLoading();
}

bool DolphinView::directoryLoading() const
{
    return m_loadingState == LoadingState::Loading;
}

bool DolphinView::isLoading() const
{
    return directoryLoading() || previewsLoading();
}

void DolphinView::stopLoading()
{
    if (!isLoading()) return;
    m_model->cancelPreviews();
    // Cancelling only previews must not change a completed listing to Canceled.
    if (directoryLoading()) m_model->cancelDirectoryLoading();
}''')
    patch('src/dolphinviewcontainer.cpp', '''    connect(m_statusBar, &DolphinStatusBar::stopPressed, this, &DolphinViewContainer::stopDirectoryLoading);''', '''    connect(m_view, &DolphinView::previewsLoadingChanged, m_statusBar, [this] {
        if (!m_view->directoryLoading()) {
            m_statusBar->showProgress(m_view->previewsLoading() ? i18nd("monet", "Loading…") : QString(),
                                      m_view->previewsLoading() ? -1 : 100);
        }
    });
    connect(m_statusBar, &DolphinStatusBar::stopPressed, this, &DolphinViewContainer::stopDirectoryLoading);''')
    patch('src/dolphinviewcontainer.cpp', '''void DolphinViewContainer::slotDirectoryLoadingCompleted()
{
    m_statusBar->showProgress(QString(), 100);''', '''void DolphinViewContainer::slotDirectoryLoadingCompleted()
{
    m_statusBar->showProgress(m_view->previewsLoading() ? i18nd("monet", "Loading…") : QString(),
                              m_view->previewsLoading() ? -1 : 100);''')
    patch('src/dolphinviewcontainer.cpp', '''        m_statusBar->showProgress(i18nc("@info:progress", "Sorting…"), percent);''', '''        if (percent == 100 && m_view->previewsLoading() && !m_view->directoryLoading()) {
            m_statusBar->showProgress(i18nd("monet", "Loading…"), -1);
        } else {
            m_statusBar->showProgress(i18nc("@info:progress", "Sorting…"), percent);
        }''')
    patch('src/dolphinmainwindow.cpp', '''    actionCollection()->action(QStringLiteral("stop"))->setEnabled(true);
}''', '''    actionCollection()->action(QStringLiteral("stop"))->setEnabled(m_activeViewContainer->view()->isLoading());
}''')
    patch('src/dolphinmainwindow.cpp', '''void DolphinMainWindow::disableStopAction()
{
    actionCollection()->action(QStringLiteral("stop"))->setEnabled(false);
}''', '''void DolphinMainWindow::disableStopAction()
{
    actionCollection()->action(QStringLiteral("stop"))->setEnabled(m_activeViewContainer->view()->isLoading());
}''')
    patch('src/dolphinmainwindow.cpp', '''    connectViewSignals(viewContainer);

    m_actionHandler->setCurrentView''', '''    connectViewSignals(viewContainer);
    disableStopAction();

    m_actionHandler->setCurrentView''')
    patch('src/dolphinmainwindow.cpp', '''    connect(view, &DolphinView::directoryLoadingStarted, this, &DolphinMainWindow::enableStopAction);''', '''    connect(view, &DolphinView::previewsLoadingChanged, this, &DolphinMainWindow::disableStopAction);
    connect(view, &DolphinView::directoryLoadingStarted, this, &DolphinMainWindow::enableStopAction);''')


if __name__ == '__main__':
    import sys
    apply(sys.argv[1])
