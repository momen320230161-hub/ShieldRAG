"""Isolated, bounded PDF/TXT parser. stdin/stdout are private pipes, not logs."""
import io
import json
import logging
import sys

MAX_BYTES = 10 * 1024 * 1024


def extract(data: bytes, extension: str, max_pages: int, max_chars: int) -> list[dict]:
    pages = []
    total = 0
    if extension == 'txt':
        text = data.decode('utf-8-sig', errors='strict').replace('\r\n', '\n').replace('\r', '\n')
        if len(text) > max_chars:
            raise ValueError('Text limit')
        return [{'page': None, 'text': text.strip()}]
    if extension != 'pdf':
        raise ValueError('Unsupported format')
    from pypdf import PdfReader, overwrite_configuration
    overwrite_configuration(zlib_maximum_output_length=20 * 1024 * 1024,
                      stream_decoding_work_maximum_length=40 * 1024 * 1024,
                      jbig2dec_binary=None)
    with PdfReader(io.BytesIO(data), strict=True, xref_stream_maximum_entries=100000) as reader:
        if reader.is_encrypted or len(reader.pages) > max_pages:
            raise ValueError('Unsupported PDF')
        for number, page in enumerate(reader.pages, 1):
            collected = 0

            def visitor(text, *_):
                nonlocal collected
                collected += len(text)
                if total + collected > max_chars:
                    raise ValueError('Text limit')

            text = page.extract_text(visitor_text=visitor) or ''
            total += len(text)
            if total > max_chars:
                raise ValueError('Text limit')
            if text.strip():
                pages.append({'page': number, 'text': text.strip()})
    return pages


def main():
    logging.disable(logging.CRITICAL)
    try:
        if sys.platform != 'win32':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            raise ValueError('File limit')
        result = extract(data, sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        sys.stdout.buffer.write(json.dumps({'pages': result}, ensure_ascii=False).encode('utf-8'))
    except Exception:
        sys.stdout.buffer.write(b'{"error":"Document extraction failed or exceeded limits"}')
        raise SystemExit(2)


if __name__ == '__main__':
    main()
