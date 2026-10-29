// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QString>

bool monetArmDeparture(const QString &token, bool armed, bool windows = false, const QString &owner = {});
bool monetFinishDeparture();
bool monetGroupDeparture();
quint64 monetDepartureGeneration();
QString monetEditorState(const QString &restore);
QString monetEditorWindows(const QString &restore);
bool monetReopenDocuments(const QString &request);
QString monetReplaceWindow(const QString &request);
void monetComplexDeparture();
