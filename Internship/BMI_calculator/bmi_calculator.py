import json
import os
from datetime import datetime

import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TrendsDialog(QDialog):
    def __init__(self, username, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"BMI Trends - {username}")
        self.resize(1000, 600)

        layout = QVBoxLayout(self)
        title = QLabel(f"BMI Trends for {username}")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        dates = [datetime.fromisoformat(entry["timestamp"]) for entry in entries]
        bmis = [entry["bmi"] for entry in entries]
        weights = [entry["weight"] for entry in entries]

        figure = Figure(figsize=(10, 8))
        figure.patch.set_facecolor("#f0f0f0")
        ax1, ax2 = figure.subplots(2, 1)

        ax1.plot(dates, bmis, marker="o", linewidth=2, markersize=8, color="#4A90E2")
        ax1.set_title("BMI Trend Over Time", fontsize=14, fontweight="bold")
        ax1.set_xlabel("Date", fontsize=12)
        ax1.set_ylabel("BMI", fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        for label in ax1.xaxis.get_majorticklabels():
            label.set_rotation(45)

        ax1.axhspan(0, 18.5, alpha=0.2, color="blue", label="Underweight")
        ax1.axhspan(18.5, 25, alpha=0.2, color="green", label="Normal")
        ax1.axhspan(25, 30, alpha=0.2, color="orange", label="Overweight")
        ax1.axhspan(30, 50, alpha=0.2, color="red", label="Obese")
        ax1.legend(loc="upper right")

        ax2.plot(dates, weights, marker="s", linewidth=2, markersize=8, color="#7ED321")
        ax2.set_title("Weight Trend Over Time", fontsize=14, fontweight="bold")
        ax2.set_xlabel("Date", fontsize=12)
        ax2.set_ylabel("Weight (kg)", fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
        for label in ax2.xaxis.get_majorticklabels():
            label.set_rotation(45)

        figure.tight_layout()

        canvas = FigureCanvasQTAgg(figure)
        layout.addWidget(canvas)

        close_button = QPushButton("Close")
        close_button.setStyleSheet("background-color: #D0021B; color: white; padding: 8px 20px;")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)


class HistoryDialog(QDialog):
    def __init__(self, username, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"BMI History - {username}")
        self.resize(850, 520)

        layout = QVBoxLayout(self)

        title = QLabel(f"BMI History for {username}")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        table = QTableWidget(len(entries), 5)
        table.setHorizontalHeaderLabels(["Date", "Weight (kg)", "Height (cm)", "BMI", "Category"])
        table.horizontalHeader().setSectionResizeMode(0, table.horizontalHeader().Stretch)
        table.horizontalHeader().setSectionResizeMode(1, table.horizontalHeader().ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, table.horizontalHeader().ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, table.horizontalHeader().ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, table.horizontalHeader().ResizeToContents)

        for row, entry in enumerate(entries):
            date_str = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            values = [
                date_str,
                str(entry["weight"]),
                str(entry["height"]),
                str(entry["bmi"]),
                entry["category"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                table.setItem(row, column, item)

        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        stats_group.setLayout(stats_layout)

        bmis = [entry["bmi"] for entry in entries]
        avg_bmi = sum(bmis) / len(bmis)
        min_bmi = min(bmis)
        max_bmi = max(bmis)
        latest_bmi = entries[-1]["bmi"]

        stats_text = (
            f"Total Entries: {len(entries)} | "
            f"Latest BMI: {latest_bmi} | "
            f"Average BMI: {avg_bmi:.2f} | "
            f"Min BMI: {min_bmi} | "
            f"Max BMI: {max_bmi}"
        )
        stats_label = QLabel(stats_text)
        stats_label.setFont(QFont("Arial", 10))
        stats_layout.addWidget(stats_label)
        layout.addWidget(stats_group)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("background-color: #D0021B; color: white; padding: 8px 20px;")
        layout.addWidget(close_button, alignment=Qt.AlignCenter)


class BMICalculatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMI Calculator - PyQt Edition")
        self.resize(900, 700)

        self.data_file = "bmi_data.json"
        self.data = self.load_data()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("BMI Calculator")
        title_font = QFont("Arial", 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        info_group = QGroupBox("User Information")
        info_layout = QFormLayout()
        info_group.setLayout(info_layout)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("Enter weight in kg")
        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("Enter height in cm")

        info_layout.addRow("Username:", self.username_input)
        info_layout.addRow("Weight (kg):", self.weight_input)
        info_layout.addRow("Height (cm):", self.height_input)
        main_layout.addWidget(info_group)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.calculate_button = QPushButton("Calculate BMI")
        self.calculate_button.setStyleSheet("background-color: #4A90E2; color: white; padding: 10px 20px;")
        self.calculate_button.clicked.connect(self.calculate_bmi_clicked)

        self.history_button = QPushButton("View History")
        self.history_button.setStyleSheet("background-color: #7ED321; color: white; padding: 10px 20px;")
        self.history_button.clicked.connect(self.view_history)

        self.trends_button = QPushButton("View Trends")
        self.trends_button.setStyleSheet("background-color: #F5A623; color: white; padding: 10px 20px;")
        self.trends_button.clicked.connect(self.view_trends)

        button_row.addWidget(self.calculate_button)
        button_row.addWidget(self.history_button)
        button_row.addWidget(self.trends_button)
        main_layout.addLayout(button_row)

        result_group = QGroupBox("BMI Result")
        result_layout = QVBoxLayout()
        result_group.setLayout(result_layout)

        self.result_label = QLabel("Enter your information and click 'Calculate BMI'")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setFont(QFont("Arial", 16))
        self.result_label.setStyleSheet("color: #666666;")
        result_layout.addWidget(self.result_label)
        main_layout.addWidget(result_group, stretch=1)

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (json.JSONDecodeError, IOError) as error:
                QMessageBox.warning(
                    self,
                    "Data Load Error",
                    f"Could not load data: {error}\nStarting with empty data.",
                )
        return {}

    def save_data(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=2)
        except IOError as error:
            QMessageBox.critical(self, "Save Error", f"Could not save data: {error}")

    @staticmethod
    def validate_input(weight_str, height_str):
        errors = []

        try:
            weight = float(weight_str)
            if weight <= 0 or weight > 500:
                errors.append("Weight must be between 0 and 500 kg")
        except ValueError:
            weight = None
            errors.append("Weight must be a valid number")

        try:
            height = float(height_str)
            if height <= 0 or height > 300:
                errors.append("Height must be between 0 and 300 cm")
        except ValueError:
            height = None
            errors.append("Height must be a valid number")

        return errors, weight, height

    @staticmethod
    def calculate_bmi(weight, height):
        height_m = height / 100
        bmi = weight / (height_m ** 2)

        if bmi < 18.5:
            category = "Underweight"
            color = "#4A90E2"
        elif bmi < 25:
            category = "Normal weight"
            color = "#7ED321"
        elif bmi < 30:
            category = "Overweight"
            color = "#F5A623"
        else:
            category = "Obese"
            color = "#D0021B"

        return round(bmi, 2), category, color

    def save_entry(self, username, weight, height, bmi, category):
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "weight": weight,
            "height": height,
            "bmi": bmi,
            "category": category,
        }

        self.data.setdefault(username, []).append(entry)
        self.save_data()

    def calculate_bmi_clicked(self):
        username = self.username_input.text().strip()
        weight_str = self.weight_input.text().strip()
        height_str = self.height_input.text().strip()

        if not username:
            QMessageBox.critical(self, "Input Error", "Please enter a username")
            return

        errors, weight, height = self.validate_input(weight_str, height_str)
        if errors:
            QMessageBox.critical(self, "Input Error", "\n".join(errors))
            return

        bmi, category, color = self.calculate_bmi(weight, height)
        self.save_entry(username, weight, height, bmi, category)

        result_text = f"BMI: {bmi}\nCategory: {category}"
        self.result_label.setText(result_text)
        self.result_label.setStyleSheet(f"color: {color};")
        self.result_label.setFont(QFont("Arial", 20, QFont.Bold))

        QMessageBox.information(self, "Success", f"BMI calculated and saved!\n\n{result_text}")

    def view_history(self):
        username = self.username_input.text().strip()

        if not username:
            QMessageBox.critical(self, "Input Error", "Please enter a username first")
            return

        entries = self.data.get(username)
        if not entries:
            QMessageBox.information(self, "No Data", f"No BMI data found for user: {username}")
            return

        dialog = HistoryDialog(username, entries, self)
        dialog.exec_()

    def view_trends(self):
        username = self.username_input.text().strip()

        if not username:
            QMessageBox.critical(self, "Input Error", "Please enter a username first")
            return

        entries = self.data.get(username)
        if not entries:
            QMessageBox.information(self, "No Data", f"No BMI data found for user: {username}")
            return

        dialog = TrendsDialog(username, entries, self)
        dialog.exec_()


def main():
    app = QApplication([])
    window = BMICalculatorWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()

