from ebooklib import epub
from bs4 import BeautifulSoup
import base64

class EPUBParser:
    def __init__(self, file_path):
        self.book = epub.read_epub(file_path)

    def extract_metadata(self):
        meta = {
            "title": self._get_meta('DC', 'title'),
            "author": self._get_meta('DC', 'creator'),
            "language": self._get_meta('DC', 'language'),
            "description": self._get_meta('DC', 'description'),
            "genre": self._get_meta('DC', 'genre'),
            "cover_image": self._extract_cover(),
            "content": self._extract_text()
        }
        return meta

    def _get_meta(self, namespace, key):
        val = self.book.get_metadata(namespace, key)
        return val[0][0] if val else None

    def _extract_cover(self):
        item = self.book.get_item_with_id('cover')
        if item:
            return base64.b64encode(item.get_content()).decode('utf-8')
        return None

    def _extract_text(self):
        text = ""
        for item in self.book.get_items_of_type(9):  # ebooklib.ITEM_DOCUMENT
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += soup.get_text(separator=' ', strip=True) + " "
        return text.strip()
