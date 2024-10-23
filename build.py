import markdown
import re
import yaml
import datetime
from pathlib import Path
from jinja2 import Template


def parse_markdown(md_file):
    with open(md_file, "r") as f:
        content = f.read()

    # Separate front matter from markdown content
    if content.startswith("---"):
        _, front_matter, markdown_content = content.split("---", 2)
        metadata = yaml.safe_load(front_matter)
    else:
        metadata = {}
        markdown_content = content

    return metadata, markdown_content


def convert_mermaid_blocks(md_content):
    # Regex to find mermaid code blocks and wrap them in a div
    pattern = r"```mermaid\s*(.*?)\s*```"
    replacement = r'<div class="mermaid">\1</div>'
    return re.sub(pattern, replacement, md_content, flags=re.DOTALL)


def render_post(md_file, template_file, header_file, footer_file):
    metadata, md_content = parse_markdown(md_file)

    md_content = convert_mermaid_blocks(md_content)

    html_content = markdown.markdown(md_content, extensions=["fenced_code"])

    with open(template_file, "r") as f:
        template = Template(f.read())

    with open(header_file, "r") as f:
        header = f.read()

    with open(footer_file, "r") as f:
        footer = f.read()

    full_content = template.render(
        title=metadata.get("title", "Untitled"),
        date=metadata.get("date", ""),
        content=html_content,
        tags=metadata.get("tags", []),
        header=header,
        footer=footer,
    )

    output_file = Path("public") / md_file.with_suffix(".html").name
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(full_content)

    return {
        "title": metadata.get("title", "Untitled"),
        "snippet": html_content.split("</p>")[0].strip("<p>"),  # Simplistic snippet
        "date": metadata.get("date", ""),
        "tags": metadata.get("tags", []),
        "url": str(output_file.relative_to("public")),
    }


def render_index(
    posts, template_file, header_file, footer_file, page_num, prev_page, next_page
):
    with open(template_file, "r") as f:
        template = Template(f.read())

    with open(header_file, "r") as f:
        header = f.read()

    with open(footer_file, "r") as f:
        footer = f.read()

    full_content = template.render(
        posts=posts,
        header=header,
        footer=footer,
        prev_page=prev_page,
        next_page=next_page,
    )

    output_file = Path("public") / (
        f"index{page_num}.html" if page_num > 1 else "index.html"
    )
    with open(output_file, "w") as f:
        f.write(full_content)


def render_rss_feed(
    posts, template_file, output_file, blog_title, blog_url, blog_description
):
    with open(template_file, "r") as f:
        template = Template(f.read())

    build_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    full_content = template.render(
        posts=posts,
        blog_title=blog_title,
        blog_url=blog_url,
        blog_description=blog_description,
        build_date=build_date,
    )

    with open(output_file, "w") as f:
        f.write(full_content)


if __name__ == "__main__":
    # Find all markdown files and render them
    posts_dir = Path("posts")
    posts_data = []
    for md_file in posts_dir.rglob("*.md"):
        post_data = render_post(
            md_file, "templates/post.html", "theme/header.html", "theme/footer.html"
        )
        posts_data.append(post_data)

    # Sort posts by date (newest first)
    posts_data.sort(key=lambda x: x["date"], reverse=True)

    # Pagination settings
    posts_per_page = 10
    total_pages = (len(posts_data) + posts_per_page - 1) // posts_per_page

    for page_num in range(1, total_pages + 1):
        start_index = (page_num - 1) * posts_per_page
        end_index = start_index + posts_per_page
        paginated_posts = posts_data[start_index:end_index]

        prev_page = f"index{page_num - 1}.html" if page_num > 1 else None
        next_page = f"index{page_num + 1}.html" if page_num < total_pages else None

        render_index(
            paginated_posts,
            "templates/index.html",
            "theme/header.html",
            "theme/footer.html",
            page_num,
            prev_page,
            next_page,
        )
        render_rss_feed(
            posts=posts_data,
            template_file="templates/rss.xml",
            output_file="public/rss.xml",
            blog_title="Lehigh Library Technology Blog",
            blog_url="https://lehigh-university-libraries.github.io/blog/",
            blog_description="",
        )
