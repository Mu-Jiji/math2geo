"""API 相关的小窗口：数字密码键盘、用户 API 预设管理。

预设窗口里的修改会直接写回主界面；API Key 和环境变量名是两个独立字段，
一个存密钥，一个存环境变量名，不要再混在一起。
"""

from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .gui import ENABLE_FREE_API, PROVIDERS, save_config

MAX_PRESETS = 10


class KeypadDialog(QDialog):
    """6 位纯数字键盘。mode=verify 校验密码，mode=set 输入新密码。"""

    def __init__(self, parent=None, passcode: str = "", auto_enter: bool = True,
                 confirm_enabled: bool = True, mode: str = "verify", title: str = "输入密码"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(320, 430)
        self.passcode = passcode
        self.auto_enter = auto_enter
        self.confirm_enabled = confirm_enabled
        self.mode = mode
        self.value = ""

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        if mode == "verify" and not passcode:
            tip_text = "请输入密码"
        elif mode == "verify":
            tip_text = "请输入密码"
        else:
            tip_text = "设置密码（0–6 位，留空则设置空密码）"
        tip = QLabel(tip_text)
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet("color:#0F3D2E; font-size:14px;")
        lay.addWidget(tip)

        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setEchoMode(QLineEdit.EchoMode.Password)
        self.display.setMaxLength(6)
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet("font-size:22px; padding:8px;")
        lay.addWidget(self.display)

        self.message = QLabel("")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet("color:#C0392B; font-size:12px;")
        lay.addWidget(self.message)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i in range(1, 10):
            btn = QPushButton(str(i))
            btn.setObjectName("Keypad")
            btn.clicked.connect(lambda _=False, d=str(i): self._press(d))
            grid.addWidget(btn, (i - 1) // 3, (i - 1) % 3)
        delete = QPushButton("删除")
        delete.setObjectName("Keypad")
        delete.clicked.connect(self._delete)
        grid.addWidget(delete, 3, 0)
        zero = QPushButton("0")
        zero.setObjectName("Keypad")
        zero.clicked.connect(lambda: self._press("0"))
        grid.addWidget(zero, 3, 1)
        confirm = QPushButton("确认")
        confirm.setObjectName("Primary")
        confirm.clicked.connect(self._confirm)
        confirm.setVisible(confirm_enabled or not auto_enter or mode == "set")
        grid.addWidget(confirm, 3, 2)
        lay.addLayout(grid)

        self.auto_check = QCheckBox("输入正确后自动进入")
        self.auto_check.setChecked(auto_enter)
        self.auto_check.setVisible(mode == "verify")
        lay.addWidget(self.auto_check)

        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)

    def _press(self, digit: str) -> None:
        if len(self.value) >= 6:
            return
        self.value += digit
        self.display.setText(self.value)
        self.message.setText("")
        auto = self.auto_check.isChecked()
        if self.mode == "verify" and auto and self.passcode:
            if len(self.value) == len(self.passcode):
                if self.value == self.passcode:
                    self.accept()
                else:
                    self._wrong()

    def _delete(self) -> None:
        self.value = self.value[:-1]
        self.display.setText(self.value)
        self.message.setText("")

    def _confirm(self) -> None:
        if self.mode == "set":
            self.accept()
            return
        if self.value == self.passcode:
            self.accept()
        else:
            self._wrong()

    def _wrong(self) -> None:
        self.value = ""
        self.display.setText("")
        self.message.setText("密码错误，请重试")


class ApiPresetManager(QDialog):
    """用户 API 预设：最多 10 个，支持新建/编辑/删除/启用与密码设置。"""

    FIELDS = ("name", "provider", "base_url", "model", "api_key", "key_env")

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.cfg = owner.cfg
        self.model = self.cfg.setdefault("model", {})
        if "api_passcode_set" not in self.model:
            self.model["api_passcode_set"] = bool(self.model.get("api_passcode"))
        self.presets: list[dict] = list(self.model.get("api_presets") or [])
        if not self.presets:
            current = self.model
            self.presets.append(
                {
                    "name": "当前配置",
                    "provider": current.get("provider", "深度求索 DeepSeek"),
                    "base_url": current.get("base_url", ""),
                    "model": current.get("name") or current.get("model", ""),
                    "api_key": current.get("api_key", ""),
                    "key_env": current.get("key_env", "MATH2GEO_API_KEY"),
                    "temperature": current.get("temperature", 0.2),
                    "max_tokens": current.get("max_tokens", 4000),
                    "timeout": current.get("timeout", 120),
                }
            )
        self.setWindowTitle("用户 API 配置")
        self.setMinimumSize(820, 560)

        outer = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._load)
        self.list.itemClicked.connect(self._preview_selected)
        left.addWidget(QLabel("API 预设（最多 10 个）"))
        left.addWidget(self.list, 1)
        btn_row = QHBoxLayout()
        for text, slot in (("新建", self._new), ("删除", self._delete)):
            b = QPushButton(text)
            b.setObjectName("Ghost")
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        left.addLayout(btn_row)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        form.setSpacing(10)
        self.ed_name = QLineEdit()
        self.ed_provider = QComboBox()
        for name, *_ in PROVIDERS:
            if name != "免费 API" or ENABLE_FREE_API:
                self.ed_provider.addItem(name)
        if ENABLE_FREE_API:
            for extra in ("ChatAnywhere（第三方）", "GitHub Summary"):
                self.ed_provider.addItem(extra)
        self.ed_base = QLineEdit()
        self.ed_model = QLineEdit()
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key = QCheckBox("显示 API Key")
        self.show_key.toggled.connect(
            lambda on: self.ed_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        self.ed_env = QLineEdit("MATH2GEO_API_KEY")
        self.ed_temp = QDoubleSpinBox()
        self.ed_temp.setRange(0.0, 2.0)
        self.ed_temp.setSingleStep(0.1)
        self.ed_tokens = QSpinBox()
        self.ed_tokens.setRange(256, 32000)
        self.ed_tokens.setSingleStep(256)
        self.ed_timeout = QSpinBox()
        self.ed_timeout.setRange(10, 600)
        for spin in (self.ed_temp, self.ed_tokens, self.ed_timeout):
            spin.lineEdit().setTextMargins(8, 0, 0, 0)
        for label, widget in (
            ("名称", self.ed_name),
            ("服务商", self.ed_provider),
            ("Base URL", self.ed_base),
            ("模型名称", self.ed_model),
            ("API Key", self.ed_key),
            ("", self.show_key),
            ("Key 环境变量", self.ed_env),
            ("Temperature", self.ed_temp),
            ("最大输出 tokens", self.ed_tokens),
            ("请求超时", self.ed_timeout),
        ):
            form.addRow(label, widget)
        right.addLayout(form)

        save = QPushButton("保存预设")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        activate = QPushButton("启用并关闭")
        activate.setObjectName("Ghost")
        activate.clicked.connect(self._activate)
        right.addWidget(save)
        right.addWidget(activate)

        # 密码设置
        pwd_box = QWidget()
        pwd_lay = QVBoxLayout(pwd_box)
        pwd_lay.setContentsMargins(0, 10, 0, 0)
        self.pwd_label = QLabel()
        pwd_lay.addWidget(self.pwd_label)
        row = QHBoxLayout()
        set_pwd = QPushButton("设置密码")
        set_pwd.setObjectName("Ghost")
        set_pwd.clicked.connect(self._set_password)
        clear_pwd = QPushButton("清除密码")
        clear_pwd.setObjectName("Ghost")
        clear_pwd.clicked.connect(self._clear_password)
        row.addWidget(set_pwd)
        row.addWidget(clear_pwd)
        row.addStretch(1)
        pwd_lay.addLayout(row)
        self.auto_check = QCheckBox("密码输入正确后自动进入")
        self.auto_check.setChecked(bool(self.model.get("api_auto_enter", True)))
        pwd_lay.addWidget(self.auto_check)
        self.confirm_check = QCheckBox("显示确认键（关闭后输入满密码长度自动提交）")
        self.confirm_check.setChecked(bool(self.model.get("api_confirm", True)))
        pwd_lay.addWidget(self.confirm_check)
        right.addWidget(pwd_box)
        right.addStretch(1)
        outer.addLayout(right, 2)

        self._syncing = False
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(250)
        self._sync_timer.timeout.connect(self._sync_current)
        for widget in (self.ed_name, self.ed_base, self.ed_model, self.ed_key, self.ed_env):
            widget.textChanged.connect(self._queue_sync)
        self.ed_provider.currentTextChanged.connect(self._queue_sync)

        for widget in (self.ed_temp, self.ed_tokens, self.ed_timeout):
            widget.valueChanged.connect(self._queue_sync)

        self._refresh_list()
        self._refresh_pwd_label()

    def _queue_sync(self, *_args) -> None:
        if self._syncing:
            return
        self._sync_timer.start()

    def _form_values(self) -> dict:
        return {
            "name": self.ed_name.text().strip() or "未命名",
            "provider": self.ed_provider.currentText(),
            "base_url": self.ed_base.text().strip(),
            "model": self.ed_model.text().strip(),
            "api_key": self.ed_key.text().strip(),
            "key_env": ("MATH2GEO_API_KEY" if (not self.ed_env.text().strip() or self.ed_env.text().strip().startswith("sk-")) else self.ed_env.text().strip()),
            "temperature": self.ed_temp.value(),
            "max_tokens": self.ed_tokens.value(),
            "timeout": self.ed_timeout.value(),
        }

    def _sync_current(self) -> None:
        p = self._current()
        if p is None:
            return
        p.update(self._form_values())
        self._save_to_cfg()
        if self.model.get("api_active") == p.get("name"):
            self._apply_to_owner(p)

    def _apply_to_owner(self, p: dict) -> None:
        owner = self.owner
        provider = p.get("provider", "")
        idx = owner.provider_combo.findText(provider)
        if idx >= 0:
            owner.provider_combo.setCurrentIndex(idx)
        owner.cloud_base.setText(p.get("base_url", ""))
        owner.cloud_name.setText(p.get("model", ""))
        owner.cloud_key.setText(p.get("api_key", ""))
        env_name = (p.get("key_env") or "").strip()
        if not env_name or env_name.startswith("sk-"):
            env_name = "MATH2GEO_API_KEY"
        owner.cloud_key_env.setText(env_name)
        owner.cloud_temp.setValue(float(p.get("temperature", 0.2)))
        owner.cloud_tokens.setValue(int(p.get("max_tokens", 4000)))
        owner.cloud_timeout.setValue(int(p.get("timeout", 120)))
        owner.cfg["model"].update(
            {
                "provider": provider,
                "base_url": p.get("base_url", ""),
                "model": p.get("model", ""),
                "name": p.get("model", ""),
                "api_key": p.get("api_key", ""),
                "key_env": p.get("key_env", "MATH2GEO_API_KEY"),
                "temperature": float(p.get("temperature", 0.2)),
                "max_tokens": int(p.get("max_tokens", 4000)),
                "timeout": int(p.get("timeout", 120)),
            }
        )
        self._save_to_cfg()

    def _refresh_pwd_label(self) -> None:
        configured = bool(self.model.get("api_passcode_set"))
        if not configured:
            self.pwd_label.setText("当前密码：未配置")
            return
        code = self.model.get("api_passcode") or ""
        self.pwd_label.setText("当前密码：已设置（空密码）" if code == "" else "当前密码：已设置")

    def _refresh_list(self, select: int | None = None) -> None:
        row = self.list.currentRow() if select is None else select
        self.list.blockSignals(True)
        self.list.clear()
        for p in self.presets:
            QListWidgetItem(p.get("name") or "未命名", self.list)
        self.list.blockSignals(False)
        if self.presets:
            self.list.setCurrentRow(max(0, min(row, len(self.presets) - 1)))

    def _current(self) -> dict | None:
        row = self.list.currentRow()
        if 0 <= row < len(self.presets):
            return self.presets[row]
        return None

    def _load(self, row: int) -> None:
        if not (0 <= row < len(self.presets)):
            return
        p = self.presets[row]
        self._syncing = True
        self.ed_name.setText(p.get("name", ""))
        self.ed_provider.setCurrentText(p.get("provider", "深度求索 DeepSeek"))
        self.ed_base.setText(p.get("base_url", ""))
        self.ed_model.setText(p.get("model", ""))
        self.ed_key.setText(p.get("api_key", ""))
        env_name = (p.get("key_env") or "").strip()
        if not env_name or env_name.startswith("sk-"):
            env_name = "MATH2GEO_API_KEY"
        self.ed_env.setText(env_name)
        self.ed_temp.setValue(float(p.get("temperature", 0.2)))
        self.ed_tokens.setValue(int(p.get("max_tokens", 4000)))
        self.ed_timeout.setValue(int(p.get("timeout", 120)))
        self._syncing = False

    def _preview_selected(self, item) -> None:
        row = self.list.row(item)
        if not (0 <= row < len(self.presets)):
            return
        p = self.presets[row]
        p.update(self._form_values())
        self.model["api_active"] = p.get("name")
        self._save_to_cfg()
        self._apply_to_owner(p)

    def _new(self) -> None:
        if len(self.presets) >= MAX_PRESETS:
            QMessageBox.information(self, "提示", "最多只能保存 10 个预设。")
            return
        self.presets.append(
            {
                "name": f"预设 {len(self.presets) + 1}",
                "provider": "深度求索 DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-flash",
                "api_key": "",
                "key_env": "MATH2GEO_API_KEY",
                "temperature": 0.2,
                "max_tokens": 4000,
                "timeout": 120,
            }
        )
        self._refresh_list()
        self.list.setCurrentRow(len(self.presets) - 1)

    def _delete(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "删除预设", "确定删除当前预设？") != QMessageBox.StandardButton.Yes:
            return
        self.presets.pop(row)
        self._save_to_cfg()
        self._refresh_list()

    def _save(self) -> None:
        p = self._current()
        if p is None:
            return
        row = self.list.currentRow()
        p.update(self._form_values())
        self._save_to_cfg()
        self._refresh_list(row)
        QMessageBox.information(self, "已保存", "API 预设已保存。")

    def _save_to_cfg(self) -> None:
        self.model["api_presets"] = self.presets
        self.model["api_auto_enter"] = self.auto_check.isChecked()
        self.model["api_confirm"] = self.confirm_check.isChecked()
        self.owner.cfg["model"].update(self.model)
        save_config(self.owner.cfg)

    def _activate(self) -> None:
        p = self._current()
        if p is None:
            return
        p.update(self._form_values())
        self.model["api_active"] = p.get("name")
        self._save_to_cfg()
        self._apply_to_owner(p)
        self.accept()

    def closeEvent(self, event) -> None:
        self._sync_current()
        active = self.model.get("api_active")
        if active:
            for p in self.presets:
                if p.get("name") == active:
                    p.update({
                        "provider": self.owner.provider_combo.currentText(),
                        "base_url": self.owner.cloud_base.text().strip(),
                        "model": self.owner.cloud_name.text().strip(),
                        "api_key": self.owner.cloud_key.text().strip(),
                        "key_env": ("MATH2GEO_API_KEY" if (not self.owner.cloud_key_env.text().strip() or self.owner.cloud_key_env.text().strip().startswith("sk-")) else self.owner.cloud_key_env.text().strip()),
                        "temperature": self.owner.cloud_temp.value(),
                        "max_tokens": self.owner.cloud_tokens.value(),
                        "timeout": self.owner.cloud_timeout.value(),
                    })
                    break
        self.model["api_auto_enter"] = self.auto_check.isChecked()
        self.model["api_confirm"] = self.confirm_check.isChecked()
        self.owner.cfg["model"].update(self.model)
        save_config(self.owner.cfg)
        super().closeEvent(event)

    def _set_password(self) -> None:
        first = KeypadDialog(self, mode="set", title="设置密码")
        if first.exec() != QDialog.DialogCode.Accepted:
            return
        if not first.value:
            self.model["api_passcode"] = ""
            self.model["api_passcode_set"] = True
            self.model["api_auto_enter"] = self.auto_check.isChecked()
            self.model["api_confirm"] = self.confirm_check.isChecked()
            self.owner.cfg["model"].update(self.model)
            save_config(self.owner.cfg)
            self._refresh_pwd_label()
            QMessageBox.information(self, "已设置", "已设置空密码：下次进入需要点「确认」才能进入。")
            return
        second = KeypadDialog(self, mode="set", title="再次输入密码")
        if second.exec() != QDialog.DialogCode.Accepted:
            return
        if first.value != second.value:
            QMessageBox.warning(self, "密码不一致", "两次输入的密码不同，请重试。")
            return
        self.model["api_passcode"] = first.value
        self.model["api_passcode_set"] = True
        self.model["api_auto_enter"] = self.auto_check.isChecked()
        self.model["api_confirm"] = self.confirm_check.isChecked()
        self.owner.cfg["model"].update(self.model)
        save_config(self.owner.cfg)
        self._refresh_pwd_label()
        QMessageBox.information(self, "已设置", "密码已保存。")

    def _clear_password(self) -> None:
        self.model["api_passcode"] = ""
        self.model["api_passcode_set"] = False
        self.owner.cfg["model"].update(self.model)
        save_config(self.owner.cfg)
        self._refresh_pwd_label()
        QMessageBox.information(self, "已清除", "密码已清除，下次进入配置界面不再弹出密码。")
