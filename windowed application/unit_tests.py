import unittest
from main import AgeClassifierApp, preprocess
import tkinter as tk

class TestAgeClassifierApp(unittest.TestCase):

    # Тестируем, что короткий текст не меняется
    def test_preprocess_short_text(self):
        short_text = "Привет"
        processed = preprocess(short_text)
        self.assertGreater(len(processed.strip()), 0, "Текст не должен быть пустым")
        self.assertEqual(processed, "привет", "Текст должен остаться без изменений")

    # Тестируем, что стоп-слова удаляются из текста
    def test_preprocess_should_remove_stopwords(self):
        text_with_stopwords = "и будет пример текста"
        processed = preprocess(text_with_stopwords)
        self.assertNotIn("и ", processed, "Стоп-слово 'и' должно быть удалено")

    # Тестируем, что лемматизация работает правильно
    def test_preprocess_should_lemmatize_words_correctly(self):
        lemmatization_text = "бежал лучший"
        processed = preprocess(lemmatization_text)
        print(processed)
        self.assertIn("бежать", processed, "Слово 'бежал' должно быть преобразовано в 'бежать'")
        self.assertIn("хороший", processed, "Слово 'лучший' должно быть преобразовано в 'хороший'")

    # Тестируем, что символ "ё" заменяется на "е"
    def test_preprocess_replace_yo(self):
        text_with_yo = "Ёлка, ёжик и морковь"
        processed = preprocess(text_with_yo)
        print(processed)
        self.assertNotIn("ё", processed)
        self.assertIn("елка", processed)

    # Тестируем, что после препроцессинга все буквы — в нижнем регистре
    def test_preprocess_all_lowercase(self):
        mixed_case_text = "ПрИвЕт МиР"
        processed = preprocess(mixed_case_text)
        # результирующая строка должна совпадать со своей же нижнерегистровой версией
        self.assertEqual(
            processed,
            processed.lower(),
            "Все буквы должны быть приведены к нижнему регистру"
        )


    # Тестируем поведение приложения с коротким текстом
    def test_predict_age_group_should_handle_short_text(self):
        app = AgeClassifierApp()
        app.text_input.insert(tk.END, "Привет")
        app.predict_age_group()
        self.assertIn("Слишком короткий текст", app.result_var.get())

    # Тестируем предсказание для длинного текста
    def test_predict_age_group_should_handle_long_text(self):
        long_text = "В каждой композиции чувствуется глубокая связь между фауной и флорой: цветы и птицы создают единый образ гармонии и природного баланса. Спасибо за вдохновение - просматривать эти фото можно бесконечно.."
        app = AgeClassifierApp()
        app.text_input.insert(tk.END, long_text)
        app.predict_age_group()
        self.assertIn("Предполагаемая группа", app.result_var.get())

if __name__ == '__main__':
    unittest.main()
