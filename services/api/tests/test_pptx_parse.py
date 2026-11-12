from io import BytesIO

from pptx import Presentation
from pptx.util import Inches, Pt

from app.knowledge.documents import parse_document


def _sample_pptx() -> bytes:
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
    box.text_frame.paragraphs[0].text = '数据库索引与 B+ 树'
    box.text_frame.paragraphs[0].font.size = Pt(28)
    slide2 = deck.slides.add_slide(deck.slide_layouts[5])
    box2 = slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
    box2.text_frame.paragraphs[0].text = 'Hash 索引适合等值查询'
    out = BytesIO()
    deck.save(out)
    return out.getvalue()


def test_parse_pptx_slides():
    pages = parse_document(_sample_pptx(), 'lecture.pptx')
    assert len(pages) == 2
    assert 'B+ 树' in pages[0].page_content
    assert pages[0].metadata['page'] == 1
    assert 'Hash' in pages[1].page_content
