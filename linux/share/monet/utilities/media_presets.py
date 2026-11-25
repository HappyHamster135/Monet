"""Local export presets for the media queue."""
import json
from uuid import uuid4

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMenu, QMessageBox

from actions import tr
from media_names import name_parts


def defaults():
    return dict(format="", quality=1, edge=0, limited=False, limit=10.0, audio=True, picture={}, pattern="")


def builtins():
    base = defaults()
    return {
        "automatic": (tr("Automatic"), base),
        "web": (tr("Web picture"), dict(base, format=".jpg", edge=1600, pattern="{name}-web", picture={"strip_metadata": True})),
        "social": (tr("Social picture"), dict(base, format=".png", edge=2048, pattern="{name}-social", picture={"strip_metadata": True})),
        "pdf": (tr("PDF handout"), dict(base, format=".pdf", edge=1600, picture={"background": "white", "keep_date": True})),
    }


def valid_recipe(recipe):
    if not isinstance(recipe, dict) or not defaults().keys() <= recipe.keys():
        return False
    def integer(value, low, high):
        return type(value) is int and low <= value <= high
    picture = recipe["picture"]
    if (recipe["format"] not in ("", ".mp4", ".gif", ".webp", ".png", ".jpg", ".heic", ".pdf")
            or not integer(recipe["quality"], 0, 2) or not integer(recipe["edge"], 0, 32768)
            or type(recipe["limited"]) is not bool or type(recipe["audio"]) is not bool
            or type(recipe["limit"]) not in (int, float) or not .01 <= recipe["limit"] <= 64000
            or not isinstance(recipe["pattern"], str) or len(recipe["pattern"]) > 240 or not isinstance(picture, dict)):
        return False
    mode = picture.get("size", "")
    if (mode not in ("", "width", "height", "exact")
            or (mode in ("width", "exact") and not integer(picture.get("width"), 1, 32768))
            or (mode in ("height", "exact") and not integer(picture.get("height"), 1, 32768))
            or any(key in picture and not integer(picture[key], 1, 32768) for key in ("width", "height"))
            or picture.get("background", "") not in ("", "white", "black")
            or type(picture.get("strip_metadata", False)) is not bool or type(picture.get("keep_date", False)) is not bool
            or picture.get("framing", "fit") not in ("fit", "fill", "stretch")
            or picture.get("position", "bottom-right") not in ("top-left", "top-right", "bottom-left", "bottom-right", "center")
            or not integer(picture.get("scale", 25), 1, 100) or not integer(picture.get("margin", 16), 0, 4096)
            or not integer(picture.get("opacity", 55), 1, 100)
            or not isinstance(picture.get("logo", ""), str) or not isinstance(picture.get("text", ""), str)
            or len(picture.get("text", "")) > 100):
        return False
    try:
        name_parts(recipe["pattern"])
    except ValueError:
        return False
    return True


class ExportMenu(QMenu):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.key = "automatic"
        self.config = QSettings("Monet", "Utilities")
        self.config.beginGroup("mediaPresets")
        self.aboutToShow.connect(self.refresh)

    def saved(self):
        self.config.sync()
        result = {}
        for key in self.config.childKeys():
            try:
                record = json.loads(self.config.value(key))
                if (isinstance(record, dict) and isinstance(record.get("name"), str) and 0 < len(record["name"].strip()) <= 80
                        and valid_recipe(record.get("settings"))):
                    result[key] = record
            except (TypeError, ValueError):
                continue
        return result

    def refresh(self):
        self.clear()
        self.addAction(tr("File names…"), self.page.edit_names)
        if not self.page.job and sum(bool(e.info) for e in self.page.entries.values()) == 1:
            self.addAction(tr("Save to folder…"), lambda: self.page.choose_output(to_folder=True))
        self.addSeparator()
        snapshot = self.page.recipe()
        saved = self.saved()
        def choice(key, name, recipe):
            action = self.addAction(name.replace("&", "&&"), lambda: self.select(key, name, recipe))
            action.setCheckable(True)
            action.setChecked(self.key == key and snapshot == recipe)
            action.setEnabled(self.page.format.findData(recipe["format"]) >= 0)
        self.addSection(tr("Presets"))
        for key, (name, recipe) in builtins().items():
            choice(key, name, recipe)
        if saved:
            self.addSection(tr("My presets"))
            for key, record in sorted(saved.items(), key=lambda item: item[1]["name"].casefold()):
                choice(key, record["name"], record["settings"])
        self.addSeparator()
        self.addAction(tr("Save as new preset…"), self.save_new)
        if self.key in saved:
            name = saved[self.key]["name"].replace("&", "&&")
            self.addAction(tr("Update “%1”").replace("%1", name), self.update_preset).setEnabled(snapshot != saved[self.key]["settings"])
            self.addAction(tr("Rename “%1”…").replace("%1", name), self.rename_preset)
            self.addAction(tr("Delete “%1”…").replace("%1", name), self.delete_preset)

    def select(self, key, name, recipe):
        self.key = key
        self.page.apply_recipe(recipe)
        self.page.message.setText(tr("Using preset “%1”.").replace("%1", name))

    def ask_name(self, initial="", key=None):
        name, accepted = QInputDialog.getText(self.page, tr("Media preset"), tr("Preset name"), QLineEdit.Normal, initial)
        if not accepted:
            return None
        name = name.strip()
        if not name or len(name) > 80:
            self.page.message.setText(tr("Use a preset name between 1 and 80 characters."))
            return None
        other_names = [record["name"] for uid, record in self.saved().items() if uid != key]
        other_names.extend(label for label, _ in builtins().values())
        if any(other.casefold() == name.casefold() for other in other_names):
            self.page.message.setText(tr("A preset already uses that name."))
            return None
        return name

    def write(self, key, name, settings):
        self.config.setValue(key, json.dumps(dict(name=name, settings=settings)))
        self.config.sync()
        if self.config.status() == QSettings.NoError:
            self.key = key
            self.page.message.setText(tr("Saved preset “%1”.").replace("%1", name))
        else:
            self.page.message.setText(tr("Couldn’t save the media preset."))

    def save_new(self):
        name = self.ask_name()
        if name:
            self.write(uuid4().hex, name, self.page.recipe())

    def update_preset(self):
        record = self.saved().get(self.key)
        if record:
            self.write(self.key, record["name"], self.page.recipe())

    def rename_preset(self):
        record = self.saved().get(self.key)
        if record:
            name = self.ask_name(record["name"], self.key)
            if name:
                self.write(self.key, name, record["settings"])

    def delete_preset(self):
        record = self.saved().get(self.key)
        if not record:
            return
        name = record["name"]
        if QMessageBox.question(self.page, tr("Delete preset"), tr("Delete the preset “%1”?").replace("%1", name),
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.config.remove(self.key)
            self.config.sync()
            if self.config.status() == QSettings.NoError:
                self.key = ""
                self.page.message.setText(tr("Deleted preset “%1”.").replace("%1", name))
            else:
                self.page.message.setText(tr("Couldn’t delete the media preset."))
