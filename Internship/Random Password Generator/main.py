import sys
import string
import secrets
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


AMBIGUOUS_CHARACTERS = {"0", "O", "o", "1", "l", "I"}
MAX_PASSWORD_LENGTH = 256
MIN_PASSWORD_LENGTH = 4


class PasswordGenerator(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Secure Password Generator")
        self.setMinimumWidth(420)
        self._password_field: QLineEdit | None = None
        self._generate_button: QPushButton | None = None
        self._copy_button: QPushButton | None = None
        self._length_input: QSpinBox | None = None
        self._exclude_input: QLineEdit | None = None
        self._options: Dict[str, QCheckBox] = {}
        self._strength_label: QLabel | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setSpacing(14)
        root_layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Generate strong, unique passwords with granular control.")
        header.setWordWrap(True)
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFont(QFont(header.font().family(), 10))
        root_layout.addWidget(header)

        form_group = QGroupBox("Password Options")
        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(12)

        self._length_input = QSpinBox()
        self._length_input.setRange(MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH)
        self._length_input.setValue(16)
        form_layout.addRow("Length", self._length_input)

        self._options = {
            "uppercase": QCheckBox("Include uppercase letters (A-Z)"),
            "lowercase": QCheckBox("Include lowercase letters (a-z)"),
            "digits": QCheckBox("Include digits (0-9)"),
            "symbols": QCheckBox("Include punctuation symbols"),
            "no_ambiguous": QCheckBox("Avoid ambiguous characters (0, O, l, 1, I)"),
            "require_all": QCheckBox("Require at least one of each selected type"),
        }

        self._options["uppercase"].setChecked(True)
        self._options["lowercase"].setChecked(True)
        self._options["digits"].setChecked(True)
        self._options["require_all"].setChecked(True)

        options_box = QGroupBox("Character Sets")
        options_layout = QVBoxLayout()
        for option_key in ("uppercase", "lowercase", "digits", "symbols"):
            options_layout.addWidget(self._options[option_key])
        options_box.setLayout(options_layout)
        form_layout.addRow(options_box)

        advanced_box = QGroupBox("Advanced Rules")
        advanced_layout = QVBoxLayout()
        advanced_layout.addWidget(self._options["no_ambiguous"])
        advanced_layout.addWidget(self._options["require_all"])
        advanced_box.setLayout(advanced_layout)
        form_layout.addRow(advanced_box)

        self._exclude_input = QLineEdit()
        self._exclude_input.setPlaceholderText("Characters to exclude (optional)")
        form_layout.addRow("Exclude characters", self._exclude_input)

        form_group.setLayout(form_layout)
        root_layout.addWidget(form_group)

        output_box = QGroupBox("Generated Password")
        output_layout = QVBoxLayout()

        self._password_field = QLineEdit()
        self._password_field.setReadOnly(True)
        self._password_field.setPlaceholderText("Click 'Generate' to create a password")
        self._password_field.setFont(QFont(self._password_field.font().family(), 11))
        output_layout.addWidget(self._password_field)

        self._strength_label = QLabel("")
        self._strength_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._strength_label.setStyleSheet("color: #555555;")
        output_layout.addWidget(self._strength_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self._generate_button = QPushButton("Generate")
        self._generate_button.clicked.connect(self._handle_generate)  # type: ignore[arg-type]
        button_row.addWidget(self._generate_button)

        self._copy_button = QPushButton("Copy to Clipboard")
        self._copy_button.setEnabled(False)
        self._copy_button.clicked.connect(self._copy_to_clipboard)  # type: ignore[arg-type]
        button_row.addWidget(self._copy_button)
        output_layout.addLayout(button_row)

        output_box.setLayout(output_layout)
        root_layout.addWidget(output_box)

        root_layout.addStretch()
        self.setLayout(root_layout)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Password Generator", message)

    def _collect_settings(self) -> Tuple[int, Dict[str, bool], List[str]]:
        if self._length_input is None:
            raise RuntimeError("Length input not initialized")

        length = int(self._length_input.value())

        enabled_sets = {
            key: bool(widget.isChecked())
            for key, widget in self._options.items()
            if key in {"uppercase", "lowercase", "digits", "symbols", "no_ambiguous", "require_all"}
        }

        exclude_chars = []
        if self._exclude_input is not None:
            exclude_chars = list({char for char in self._exclude_input.text()})

        return length, enabled_sets, exclude_chars

    def _handle_generate(self) -> None:
        try:
            length, options, exclusions = self._collect_settings()
            password = self._generate_password(length, options, exclusions)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        if self._password_field is not None:
            self._password_field.setText(password)
        if self._copy_button is not None:
            self._copy_button.setEnabled(True)

        if self._strength_label is not None:
            self._strength_label.setText(f"Strength: {self._estimate_strength(password)}")

    def _generate_password(
        self,
        length: int,
        options: Dict[str, bool],
        exclusions: List[str],
    ) -> str:
        if length < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password length must be at least {MIN_PASSWORD_LENGTH}.")
        if length > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password length must not exceed {MAX_PASSWORD_LENGTH}.")

        char_sets = {
            "uppercase": set(string.ascii_uppercase),
            "lowercase": set(string.ascii_lowercase),
            "digits": set(string.digits),
            "symbols": set("!@#$%^&*()-_=+[]{};:,.<>?/|`~"),
        }

        selected_sets = {
            key: values
            for key, values in char_sets.items()
            if options.get(key, False)
        }
        if not selected_sets:
            raise ValueError("Select at least one character set.")

        combined_chars = set().union(*selected_sets.values())

        if options.get("no_ambiguous", False):
            combined_chars -= AMBIGUOUS_CHARACTERS
            for key in selected_sets:
                selected_sets[key] = selected_sets[key] - AMBIGUOUS_CHARACTERS

        if exclusions:
            to_remove = set(exclusions)
            combined_chars -= to_remove
            for key in selected_sets:
                selected_sets[key] = selected_sets[key] - to_remove

        if not combined_chars:
            raise ValueError("Character pool is empty. Adjust your selections or exclusions.")

        password_chars: List[str] = []

        if options.get("require_all", False):
            required_categories = [
                secrets.choice(list(characters))
                for characters in selected_sets.values()
                if characters
            ]
            if len(required_categories) > length:
                raise ValueError(
                    "Password length is too short to include all required character types."
                )
            password_chars.extend(required_categories)

        remaining_length = length - len(password_chars)
        pool = list(combined_chars)
        for _ in range(remaining_length):
            password_chars.append(secrets.choice(pool))

        secrets.SystemRandom().shuffle(password_chars)
        return "".join(password_chars)

    def _estimate_strength(self, password: str) -> str:
        length = len(password)
        diversity = sum([
            bool(set(password) & set(string.ascii_lowercase)),
            bool(set(password) & set(string.ascii_uppercase)),
            bool(set(password) & set(string.digits)),
            bool(set(password) & set("!@#$%^&*()-_=+[]{};:,.<>?/|`~")),
        ])

        if length >= 16 and diversity >= 3:
            return "Excellent"
        if length >= 12 and diversity >= 3:
            return "Strong"
        if length >= 10 and diversity >= 2:
            return "Moderate"
        if length >= 8:
            return "Weak"
        return "Very Weak"

    def _copy_to_clipboard(self) -> None:
        if self._password_field is None:
            return
        password = self._password_field.text()
        if not password:
            self._show_error("Generate a password before copying.")
            return
        QApplication.clipboard().setText(password)
        self._show_info("Password copied to clipboard.")

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Password Generator", message)


def main() -> None:
    app = QApplication(sys.argv)
    window = PasswordGenerator()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

