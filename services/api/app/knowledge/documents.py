from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentError(ValueError):
    pass


SUPPORTED = {".pdf", ".docx", ".txt", ".pptx", ".ppt"}
MAX_TEXT = 800_000


def _parse_pptx(data: bytes, filename: str) -> list[Document]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    with ZipFile(BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 120 * 1024 * 1024:
            raise DocumentError("PPT 解压后过大，请拆分后上传。")
    try:
        deck = Presentation(BytesIO(data))
    except Exception as exc:
        raise DocumentError("无法打开 PPTX，请确认文件未损坏。") from exc
    if len(deck.slides) > 200:
        raise DocumentError("单份 PPT 最多支持 200 页，请拆分后上传。")
    pages: list[Document] = []
    total = 0
    for index, slide in enumerate(deck.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = "\n".join(p.text.strip() for p in shape.text_frame.paragraphs if p.text and p.text.strip())
                if text:
                    lines.append(text)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
                    if cells:
                        lines.append(" | ".join(cells))
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                continue
            if getattr(shape, "has_chart", False):
                lines.append("[图表]")
        content = "\n".join(lines).strip()
        total += len(content)
        if total > MAX_TEXT:
            raise DocumentError("文字超过 80 万字符，请拆分文档。")
        if content:
            pages.append(Document(
                page_content=content,
                metadata={"page": index, "section": f"第 {index} 页幻灯片", "filename": filename},
            ))
    return pages


def parse_document(data: bytes, filename: str) -> list[Document]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise DocumentError("支持 PDF、Word（.docx）、PPT（.pptx）和 TXT；旧版 .ppt/.doc 请先另存为 .pptx/.docx。")
    if not data:
        raise DocumentError("文件为空，请选择包含文字的文档。")
    pages = []
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise DocumentError("暂不支持加密 PDF，请先提供未加密版本。")
            if len(reader.pages) > 300:
                raise DocumentError("单份 PDF 最多支持 300 页，请拆分后上传。")
            total = 0
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                total += len(text)
                if total > MAX_TEXT:
                    raise DocumentError("文字超过 80 万字符，请拆分文档。")
                if text.strip():
                    pages.append(Document(page_content=text.strip(), metadata={"page": i + 1, "section": None}))
        elif suffix == ".docx":
            from docx import Document as WordDocument
            from docx.table import Table

            with ZipFile(BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                    raise DocumentError("Word 文件解压后过大，请拆分后上传。")
            word = WordDocument(BytesIO(data))
            blocks = []
            for item in word.iter_inner_content():
                if isinstance(item, Table):
                    blocks.extend(" | ".join(cell.text for cell in row.cells) for row in item.rows)
                else:
                    blocks.append(item.text)
            text = "\n\n".join(block for block in blocks if block.strip())
            pages.append(Document(page_content=text, metadata={"page": None, "section": "Word 正文"}))
        elif suffix == ".pptx":
            pages.extend(_parse_pptx(data, filename))
        elif suffix == ".ppt":
            raise DocumentError("暂不支持旧版二进制 .ppt，请在 PowerPoint 中另存为 .pptx 后再上传。")
        else:
            if b"\x00" in data:
                raise DocumentError("TXT 包含二进制内容，请使用 UTF-8 或 GB18030 编码的纯文本。")
            text = None
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    pass
            if text is None:
                raise DocumentError("无法识别文本编码，请将文件另存为 UTF-8。")
            pages.append(Document(page_content=text, metadata={"page": None, "section": "TXT 正文"}))
    except DocumentError:
        raise
    except (Exception, BadZipFile) as exc:
        raise DocumentError("文件无法解析，请检查是否损坏，或是否更改过文件扩展名。") from exc
    if not pages or not any(p.page_content.strip() for p in pages):
        raise DocumentError("未提取到文字；扫描版 PDF 需要先做 OCR，本版本暂未集成 OCR。")
    if sum(len(p.page_content) for p in pages) > MAX_TEXT:
        raise DocumentError("文字超过 80 万字符，请拆分文档。")
    for page in pages:
        page.metadata["filename"] = filename
    return pages


def chunk_documents(pages: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900, chunk_overlap=140,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
        add_start_index=True,
    )
    chunks = splitter.split_documents(pages)
    for position, chunk in enumerate(chunks):
        chunk.metadata["position"] = position
        if chunk.metadata.get("page") is None:
            chunk.metadata["section"] = f"正文片段 {position + 1}"
    return chunks
