import pathlib

import markdown as md
from weasyprint import HTML


def generate_resume_pdf(resume_md: str, output_path: str | pathlib.Path) -> pathlib.Path:
    html = md.markdown(resume_md)
    HTML(string=html).write_pdf(str(output_path))
    return pathlib.Path(output_path)
