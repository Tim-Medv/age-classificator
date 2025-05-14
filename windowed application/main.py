import re
import ssl
import joblib
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
from pathlib import Path

import numpy as np
import pandas as pd
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from pymorphy2 import MorphAnalyzer

# Загружаем русские стоп-слова из NLTK
try:
    _ = stopwords.words("russian")
except LookupError:
    ssl._create_default_https_context = ssl._create_unverified_context
    nltk.download("stopwords")

# Путь к файлу сохранённой модели
MODEL_PATH = Path(__file__).parent / "age_classifier_pipeline.pkl"
if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Модель не найдена: {MODEL_PATH}")

# Загрузка обученного пайплайна
model = joblib.load(MODEL_PATH)

# Настройка морфологического анализатора и списков стоп-слов
MORPH = MorphAnalyzer()
RU_STOP = set(stopwords.words("russian"))
EN_STOP = ENGLISH_STOP_WORDS

#Лемматизация и удаление стоп-слов (русских и английских). Возвращает строку очищенных токенов.
def preprocess(text,
               _morph=MORPH,
               _en_stop=EN_STOP,
               _ru_stop=RU_STOP):

    text = str(text).lower().replace('ё', 'е')
    tokens = re.findall(r'[a-zа-я]+', text)

    cleaned = []
    for tok in tokens:
        if re.fullmatch(r'[a-z]+', tok):
            if tok not in _en_stop:
                cleaned.append(tok)
        else:
            if tok in _ru_stop:
                continue
            lemma = _morph.parse(tok)[0].normal_form
            lemma = lemma.replace('ё', 'е')
            if lemma not in _ru_stop:
                cleaned.append(lemma)

    return ' '.join(cleaned)




class AgeClassifierApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Определитель возрастной группы по тексту")
        self.geometry("720x520")
        self.configure(bg="#2e3440")
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        # Настройка стилей
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background='#2e3440')
        style.configure('TLabel', background='#2e3440', foreground='#eceff4', font=('Segoe UI', 12))
        style.configure('TButton', font=('Segoe UI', 12), padding=8,
                        background='#5e81ac', foreground='#eceff4')
        style.map('TButton', background=[('active', '#81a1c1')])
        style.configure('Result.TLabel', background='#eceff4', foreground='#2e3440',
                        font=('Segoe UI', 12), relief='solid', padding=10)

    def _create_widgets(self):
        # Поле ввода текста
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        label = ttk.Label(frame, text="Введите текст для анализа:")
        label.pack(anchor='w', pady=(0, 10))

        self.text_input = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, height=12, font=('Consolas', 11),
            bg='#3b4252', fg='#eceff4', insertbackground='#eceff4',
            selectbackground='#88c0d0'
        )
        self.text_input.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Кнопка для запуска предсказания
        button = ttk.Button(self, text="Определить возрастную группу",
                            command=self.predict_age_group)
        button.pack(pady=(0, 15))

        # Место для вывода результата
        self.result_var = tk.StringVar()
        result_label = ttk.Label(self, textvariable=self.result_var,
                                 style='Result.TLabel', wraplength=680,
                                 justify=tk.LEFT)
        result_label.pack(fill=tk.BOTH, padx=15, pady=(0, 15))

    def predict_age_group(self) -> None:
        # Получаем текст из поля и очищаем его
        raw_text = self.text_input.get("1.0", tk.END).strip()
        cleaned = preprocess(raw_text)
        tokens = cleaned.split()

        # Проверяем достаточность слов для анализа
        if len(tokens) < 15:
            self.result_var.set("Слишком короткий текст. Недостаточно значимых слов для анализа.")
            return

        X_input = pd.DataFrame({"comment": [cleaned]})

        # Делаем предсказание
        try:
            pred = model.predict(X_input)[0]
        except Exception as e:
            self.result_var.set(f"Ошибка модели: {e}")
            return

        message = f"Предполагаемая группа: {pred}"
        self.result_var.set(message)


if __name__ == "__main__":
    app = AgeClassifierApp()
    app.mainloop()