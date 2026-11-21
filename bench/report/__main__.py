import argparse
import os
import sys
from pathlib import Path

from bench.report import document, slides


def main():
    parser = argparse.ArgumentParser(description="Buduje sprawozdanie DOCX i PDF oraz prezentację PPTX")
    parser.add_argument("--results", type=Path, default=Path(os.environ.get("RESULTS_DIR", "results")))
    parser.add_argument("--out", type=Path, default=Path("out"))
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)
    outputs = [arguments.out / name for name in ("sprawozdanie.docx", "sprawozdanie.pdf", "prezentacja.pptx")]
    for path in outputs:
        path.unlink(missing_ok=True)
    try:
        document.build(arguments.results, arguments.out)
    except document.ReportError as error:
        sys.exit(str(error))
    slides.build(arguments.results, outputs[2])
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
