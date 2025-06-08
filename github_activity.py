import sys
import os
import json
import random
import subprocess
import webbrowser
import shutil
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QGridLayout, QInputDialog, QFileDialog, QMessageBox, QStackedWidget, QSpinBox, QProgressBar, QDateEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QIcon
class DayWidget(QLabel):
    def __init__(self, date_str, commits, on_change, draw_mode_ref, draw_value_ref, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.date_str = date_str
        self.commits = commits
        self.on_change = on_change
        self.draw_mode_ref = draw_mode_ref
        self.draw_value_ref = draw_value_ref
        self.setFixedSize(14, 14)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(f"{date_str}: {commits} коммит(ов)")
        self.update_color()
    def update_color(self):
        colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
        if self.commits == 0:
            color = colors[0]
        elif self.commits == 1:
            color = colors[1]
        elif self.commits <= 3:
            color = colors[2]
        elif self.commits <= 6:
            color = colors[3]
        else:
            color = colors[4]
        self.setStyleSheet(f"background-color: {color}; border-radius: 3px; border: 1px solid #222; color: #fff;")
        self.setText("")
        self.setToolTip(f"{self.date_str}: {self.commits} коммит(ов)")
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.draw_mode_ref() and self.draw_value_ref() is not None:
                self.commits = self.draw_value_ref()
                self.update_color()
                self.on_change(self.date_str, self.commits)
                self.parentWidget().parentWidget().parentWidget()._drawing = True
            else:
                value, ok = QInputDialog.getInt(self, "Изменить количество коммитов", f"{self.date_str}", self.commits, 0, 100, 1)
                if ok:
                    self.commits = value
                    self.update_color()
                    self.on_change(self.date_str, value)
    def enterEvent(self, event):
        mainwin = self.parentWidget().parentWidget().parentWidget()
        if getattr(mainwin, '_drawing', False) and self.draw_mode_ref() and self.draw_value_ref() is not None:
            self.commits = self.draw_value_ref()
            self.update_color()
            self.on_change(self.date_str, self.commits)
        super().enterEvent(event)
class CommitWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    def __init__(self, username, email, repo_url, pattern, work_dir):
        super().__init__()
        self.username = username
        self.email = email
        self.repo_url = repo_url
        self.pattern = pattern
        self.work_dir = work_dir
    def run(self):
        try:
            if os.path.exists(self.work_dir):
                try:
                    shutil.rmtree(self.work_dir)
                except PermissionError as e:
                    if hasattr(e, 'winerror') and e.winerror == 5:
                        self.finished.emit(False, "Ошибка доступа к папке gh_activity_repo!\n\nЗакройте все программы, которые могут использовать папку gh_activity_repo (Проводник Windows, редакторы, git bash и т.д.).\nПопробуйте вручную удалить папку gh_activity_repo и повторите попытку.")
                        return
                    else:
                        self.finished.emit(False, f"Ошибка удаления папки: {e}")
                        return
            os.makedirs(self.work_dir, exist_ok=True)
            subprocess.run(["git", "init"], cwd=self.work_dir)
            subprocess.run(["git", "config", "user.name", self.username], cwd=self.work_dir)
            subprocess.run(["git", "config", "user.email", self.email], cwd=self.work_dir)
            dummy_file = os.path.join(self.work_dir, "dummy.txt")
            total = sum(self.pattern.values())
            done = 0
            for date_str, count in self.pattern.items():
                for i in range(count):
                    with open(dummy_file, "a", encoding="utf-8") as f:
                        f.write(f"{date_str} commit {i+1}\n")
                    subprocess.run(["git", "add", "dummy.txt"], cwd=self.work_dir)
                    env = os.environ.copy()
                    env["GIT_AUTHOR_DATE"] = f"{date_str}T12:00:00"
                    env["GIT_COMMITTER_DATE"] = f"{date_str}T12:00:00"
                    subprocess.run([
                        "git", "commit", "-m", f"Commit for {date_str} #{i+1}"
                    ], cwd=self.work_dir, env=env)
                    done += 1
                    self.progress.emit(int(done / total * 100))
            subprocess.run(["git", "branch", "-M", "main"], cwd=self.work_dir)
            subprocess.run(["git", "remote", "add", "origin", self.repo_url], cwd=self.work_dir)
            result = subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=self.work_dir, capture_output=True, text=True)
            if result.returncode == 0:
                self.finished.emit(True, "Коммиты успешно созданы и запушены!")
            else:
                self.finished.emit(False, f"Ошибка при push:\n{result.stderr}")
        except Exception as e:
            self.finished.emit(False, str(e))
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор Активности GitHub")
        self.setMinimumSize(900, 500)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GitHub_activity.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.pattern = {}
        self.draw_mode = False
        self.draw_value = 1
        self._drawing = False
        self.init_ui()
    def init_ui(self):
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)
        self.init_screen1()
        self.init_screen2()
        self.stacked.setCurrentIndex(0)
    def init_screen1(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        font = QFont()
        font.setPointSize(16)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Никнейм")
        self.username_input.setFont(font)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Электронная почта")
        self.email_input.setFont(font)
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("URL репозитория")
        self.repo_input.setFont(font)
        self.next_btn = QPushButton("Далее")
        self.next_btn.setEnabled(False)
        self.next_btn.setFont(font)
        self.next_btn.setMinimumHeight(40)
        self.next_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.username_input.textChanged.connect(self.check_fields)
        self.email_input.textChanged.connect(self.check_fields)
        self.repo_input.textChanged.connect(self.check_fields)
        label = QLabel("Введите данные для GitHub:")
        label.setFont(font)
        layout.addWidget(label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.email_input)
        layout.addWidget(self.repo_input)
        self.create_repo_btn = QPushButton("Создать репозиторий на GitHub")
        self.create_repo_btn.setFont(font)
        self.create_repo_btn.setMinimumHeight(36)
        self.create_repo_btn.clicked.connect(self.open_github_repos)
        layout.addWidget(self.create_repo_btn)
        tip = QLabel("1. Введите свой никнейм и электронную почту.\n"
                     "2. Нажмите на кнопку выше — откроется страница ваших репозиториев на GitHub.\n"
                     "3. Нажмите 'New' или 'Создать репозиторий'.\n"
                     "3. После создания скопируйте ссылку на репозиторий (например, https://github.com/USERNAME/REPO.git) и вставьте её в поле выше.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(tip)
        layout.addWidget(self.next_btn)
        layout.addStretch()
        self.stacked.addWidget(w)
    def check_fields(self):
        if self.username_input.text() and self.email_input.text() and self.repo_input.text():
            self.next_btn.setEnabled(True)
        else:
            self.next_btn.setEnabled(False)
    def init_screen2(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        draw_layout = QHBoxLayout()
        self.draw_checkbox = QCheckBox("Рисование мышкой")
        self.draw_checkbox.stateChanged.connect(self.toggle_draw_mode)
        draw_layout.addWidget(self.draw_checkbox)
        draw_layout.addWidget(QLabel("Значение:"))
        self.draw_spin = QSpinBox()
        self.draw_spin.setRange(0, 100)
        self.draw_spin.setValue(1)
        self.draw_spin.valueChanged.connect(self.set_draw_value)
        draw_layout.addWidget(self.draw_spin)
        vbox.addLayout(draw_layout)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(180)
        self.scroll_widget = QWidget()
        self.calendar_layout = QGridLayout(self.scroll_widget)
        self.calendar_layout.setHorizontalSpacing(2)
        self.calendar_layout.setVerticalSpacing(2)
        self.draw_calendar()
        self.scroll_area.setWidget(self.scroll_widget)
        vbox.addWidget(self.scroll_area)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        vbox.addWidget(self.progress_bar)
        btns = QHBoxLayout()
        btn_font = QFont()
        btn_font.setPointSize(15)
        self.btn_list = []
        for text, slot in [
            ("Сбросить", self.reset_calendar),
            ("Автомат", self.auto_fill),
            ("Создать комиты", self.create_commits),
            ("Сохранить шаблон", self.save_pattern),
            ("Загрузить шаблон", self.load_pattern)
        ]:
            btn = QPushButton(text)
            btn.setFont(btn_font)
            btn.setMinimumHeight(38)
            btn.clicked.connect(slot)
            btns.addWidget(btn)
            self.btn_list.append(btn)
        vbox.addLayout(btns)
        hotkey_tip = QLabel("Горячие клавиши: Ctrl+S — сохранить, Ctrl+O — открыть, 1-9 — задать значение для рисования, Esc — выключить рисование")
        hotkey_tip.setStyleSheet("color: #aaa; font-size: 13px;")
        vbox.addWidget(hotkey_tip)
        self.stacked.addWidget(w)
    def draw_calendar(self):
        for i in reversed(range(self.calendar_layout.count())):
            item = self.calendar_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        months = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
        month_positions = {}
        start_date = (QDate.currentDate().addDays(-364)).toPyDate()
        end_date = QDate.currentDate().toPyDate()
        current_date = start_date
        day_of_week = current_date.weekday()
        while day_of_week != 0:
            current_date -= timedelta(days=1)
            day_of_week = current_date.weekday()
        prev_month = current_date.month
        month_positions[current_date.strftime('%b')] = 0
        date_matrix = []
        for col in range(53):
            week_col = []
            for row in range(7):
                if current_date > end_date:
                    break
                date_str = current_date.strftime("%Y-%m-%d")
                week_col.append(date_str)
                if (current_date.day == 1 and current_date.month != prev_month) or (col == 0 and row == 0):
                    month_positions[current_date.strftime('%b')] = col
                    prev_month = current_date.month
                current_date += timedelta(days=1)
            date_matrix.append(week_col)
            if current_date > end_date:
                break
        for m, col in month_positions.items():
            label = QLabel(m)
            label.setStyleSheet("color: #aaa; font-size: 12px;")
            self.calendar_layout.addWidget(label, 0, col+1, 1, 4, alignment=Qt.AlignmentFlag.AlignLeft)
        week_days = ["Пн", "Ср", "Пт"]
        week_rows = [1, 3, 5]
        for i, wd in enumerate(week_days):
            label = QLabel(wd)
            label.setStyleSheet("color: #aaa; font-size: 12px;")
            self.calendar_layout.addWidget(label, week_rows[i]+1, 0, alignment=Qt.AlignmentFlag.AlignRight)
        for col, week_col in enumerate(date_matrix):
            for row, date_str in enumerate(week_col):
                if row > 6:
                    continue
                commits = self.pattern.get(date_str, 0)
                day_widget = DayWidget(date_str, commits, self.update_commit_count, lambda: self.draw_mode, lambda: self.draw_value)
                self.calendar_layout.addWidget(day_widget, row+1, col+1)
    def update_commit_count(self, date_str, count):
        self.pattern[date_str] = count
    def reset_calendar(self):
        self.pattern = {}
        self.draw_calendar()
    def auto_fill(self):
        min_val, ok1 = QInputDialog.getInt(self, "Минимум коммитов", "Минимум:", 0, 0, 100, 1)
        if not ok1:
            return
        max_val, ok2 = QInputDialog.getInt(self, "Максимум коммитов", "Максимум:", 10, min_val, 100, 1)
        if not ok2:
            return
        start_date = datetime.now() - timedelta(days=364)
        current_date = start_date
        day_of_week = current_date.weekday()
        while day_of_week != 0:
            current_date -= timedelta(days=1)
            day_of_week = current_date.weekday()
        while current_date <= datetime.now():
            date_str = current_date.strftime("%Y-%m-%d")
            self.pattern[date_str] = random.randint(min_val, max_val)
            current_date += timedelta(days=1)
        self.draw_calendar()
    def create_commits(self):
        if shutil.which("git") is None:
            QMessageBox.critical(self, "Git не найден", "На вашем компьютере не установлен git!\n\nПожалуйста, скачайте и установите git с https://git-scm.com/ и повторите попытку.")
            return
        username = self.username_input.text()
        email = self.email_input.text()
        repo_url = self.repo_input.text()
        if not username or not email or not repo_url:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, заполните все поля на первом экране!")
            return
        self.set_buttons_enabled(False)
        self.progress_bar.setValue(0)
        work_dir = os.path.join(os.getcwd(), "gh_activity_repo")
        self.worker = CommitWorker(username, email, repo_url, self.pattern, work_dir)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_commits_finished)
        self.worker.start()
    def on_commits_finished(self, success, message):
        self.set_buttons_enabled(True)
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
    def save_pattern(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить шаблон", "", "JSON файлы (*.json)")
        if file_name:
            with open(file_name, 'w') as f:
                json.dump(self.pattern, f, indent=2)
    def load_pattern(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Загрузить шаблон", "", "JSON файлы (*.json)")
        if file_name:
            with open(file_name, 'r') as f:
                self.pattern = json.load(f)
            self.draw_calendar()
    def set_buttons_enabled(self, enabled):
        for btn in self.btn_list:
            btn.setEnabled(enabled)
    def open_github_repos(self):
        username = self.username_input.text().strip()
        if username:
            url = f"https://github.com/{username}?tab=repositories"
        else:
            url = "https://github.com/"
        webbrowser.open(url)
    def toggle_draw_mode(self, state):
        self.draw_mode = bool(state)
    def set_draw_value(self, value):
        self.draw_value = value
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.draw_mode:
            self._drawing = True
        super().mousePressEvent(event)
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
        super().mouseReleaseEvent(event)
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_S:
                self.save_pattern()
            elif event.key() == Qt.Key.Key_O:
                self.load_pattern()
        elif Qt.Key.Key_1 <= event.key() <= Qt.Key.Key_9:
            self.draw_spin.setValue(event.key() - Qt.Key.Key_0)
        elif event.key() == Qt.Key.Key_Escape:
            self.draw_checkbox.setChecked(False)
        super().keyPressEvent(event)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())