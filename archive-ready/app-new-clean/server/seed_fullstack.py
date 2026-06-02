"""
Seed script: Import Fullstack Web Developer - ONE course, 4 blocks as sections.
Content is formatted into beautiful rich HTML with headings, bold, italic, lists, tables, blockquotes.
"""
import json
import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, delete
from app.database import async_session, init_db
from app.models.user import User, UserRole
from app.models.training import (
    TrainingCourse, TrainingTopic, TrainingContent,
    TrainingTask, TrainingSubmission, CourseAssignment,
    TopicProgress, Hashtag, topic_hashtags,
)

BLOCKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_parsed_blocks.json")
if not os.path.exists(BLOCKS_JSON):
    BLOCKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_parsed_blocks.json")

COURSE_TITLE = "Fullstack Web-Developer"
COURSE_DESC = "Comprehensive fullstack web development program: IT fundamentals, no-code (Tilda), frontend (HTML/CSS/JS/TS), backend (Node.js, Express, PostgreSQL, MongoDB), architecture and DevOps."

BLOCK_NAMES = {
    0: "Block 0. IT Fundamentals",
    1: "Block 1. Quick Start: Tilda",
    2: "Block 2. Web Development",
    3: "Block 3. Architecture & Backend",
}


# ============ RICH HTML FORMATTER ============

def format_theory(raw):
    if not raw or not raw.strip():
        return ""
    lines = raw.strip().split('\n')
    html_parts = []
    i = 0
    in_list = False
    list_type = None

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            if in_list:
                html_parts.append('</%s>' % list_type)
                in_list = False
                list_type = None
            i += 1
            continue

        stripped = line.strip()

        # Detect numbered heading patterns
        heading_match = re.match(r'^(\d+)\.\s+([A-ZА-ЯЁ][\w\s\-\(\),.:\/]+)', stripped)
        if heading_match and len(stripped) < 120:
            if in_list:
                html_parts.append('</%s>' % list_type)
                in_list = False
                list_type = None
            html_parts.append('<h3>%s</h3>' % _escape(stripped))
            i += 1
            continue

        # Detect bullet points
        bullet_match = re.match(r'^[\u2022\u2023\u25E6\u2043\u2219\xB7\-\*]\s+', stripped)
        sub_match = re.match(r'^[а-яa-z]\)\s+', stripped)

        if bullet_match or sub_match:
            content = re.sub(r'^[\u2022\u2023\u25E6\u2043\u2219\xB7\-\*а-яa-z\d\)]+[\s\.]*', '', stripped).strip()
            if not in_list or list_type != 'ul':
                if in_list:
                    html_parts.append('</%s>' % list_type)
                html_parts.append('<ul>')
                in_list = True
                list_type = 'ul'
            html_parts.append('<li>%s</li>' % _format_inline(content))
            i += 1
            continue

        # Numbered list continuation
        numlist_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if numlist_match and in_list and list_type == 'ol':
            html_parts.append('<li>%s</li>' % _format_inline(numlist_match.group(2).strip()))
            i += 1
            continue

        # Start numbered list
        if numlist_match and not heading_match:
            next_i = i + 1
            is_list = False
            while next_i < len(lines) and next_i - i < 5:
                nl = lines[next_i].strip()
                if not nl:
                    next_i += 1
                    continue
                if re.match(r'^(\d+)\.\s+', nl):
                    is_list = True
                break
            if is_list:
                if in_list:
                    html_parts.append('</%s>' % list_type)
                html_parts.append('<ol>')
                in_list = True
                list_type = 'ol'
                html_parts.append('<li>%s</li>' % _format_inline(numlist_match.group(2).strip()))
                i += 1
                continue

        # Close any open list
        if in_list:
            html_parts.append('</%s>' % list_type)
            in_list = False
            list_type = None

        # Definition line with dash
        defn_match = re.match(r'^(.+?)\s*[\u2014\u2013\u2012]+\s+(.+)', stripped)
        if defn_match and len(defn_match.group(1)) < 80:
            term = defn_match.group(1).strip()
            defn = defn_match.group(2).strip()
            html_parts.append('<p><strong>%s</strong> &mdash; %s</p>' % (_escape(term), _format_inline(defn)))
            i += 1
            continue

        # Regular paragraph
        html_parts.append('<p>%s</p>' % _format_inline(stripped))
        i += 1

    if in_list:
        html_parts.append('</%s>' % list_type)

    return '\n'.join(html_parts)


def format_practice(raw):
    if not raw or not raw.strip():
        return ""
    lines = raw.strip().split('\n')
    html_parts = []
    i = 0
    in_list = False

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            if in_list:
                html_parts.append('</ol>')
                in_list = False
            i += 1
            continue

        # Task header
        task_match = re.match(r'^(Задание\s*\d*)[:\.]?\s*(.*)', line, re.IGNORECASE)
        if task_match:
            if in_list:
                html_parts.append('</ol>')
                in_list = False
            title = task_match.group(1)
            rest = task_match.group(2) or ''
            html_parts.append('<blockquote><strong>%s</strong>' % _escape(title))
            if rest:
                html_parts.append('<br/>%s' % _format_inline(rest))
            html_parts.append('</blockquote>')
            i += 1
            continue

        # Numbered step
        num_match = re.match(r'^(\d+)[\.\)]\s+(.+)', line)
        if num_match:
            if not in_list:
                html_parts.append('<ol>')
                in_list = True
            html_parts.append('<li>%s</li>' % _format_inline(num_match.group(2)))
            i += 1
            continue

        # Bullet
        bullet_match = re.match(r'^[\u2022\u2023\u2219\xB7\-\*]\s+(.+)', line)
        if bullet_match:
            if in_list:
                html_parts.append('</ol>')
                in_list = False
            html_parts.append('<p>&#8226; %s</p>' % _format_inline(bullet_match.group(1)))
            i += 1
            continue

        if in_list:
            html_parts.append('</ol>')
            in_list = False

        html_parts.append('<p>%s</p>' % _format_inline(line))
        i += 1

    if in_list:
        html_parts.append('</ol>')

    return '\n'.join(html_parts)


def format_test(raw):
    if not raw or not raw.strip():
        return ""
    lines = raw.strip().split('\n')
    html_parts = []
    i = 0
    in_question = False
    in_options = False

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            if in_options:
                html_parts.append('</div>')
                in_options = False
            i += 1
            continue

        q_match = re.match(r'^(Вопрос\s*\d*)[:\.]?\s*(.*)', line, re.IGNORECASE)
        if q_match:
            if in_options:
                html_parts.append('</div>')
                in_options = False
            if in_question:
                html_parts.append('</div>')
            html_parts.append('<div style="margin-bottom:16px;padding:14px 18px;border:1px solid #e2e8f0;border-radius:10px;background:#fafbfd">')
            html_parts.append('<p style="font-weight:600;margin-bottom:8px">%s. %s</p>' % (_escape(q_match.group(1)), _format_inline(q_match.group(2) or '')))
            in_question = True
            i += 1
            continue

        opt_match = re.match(r'^([а-гa-d])\)\s+(.+)', line, re.IGNORECASE)
        if opt_match:
            if not in_options:
                html_parts.append('<div style="display:flex;flex-direction:column;gap:4px">')
                in_options = True
            html_parts.append('<div style="padding:5px 10px;border-radius:6px;font-size:14px">%s) %s</div>' % (_escape(opt_match.group(1)), _format_inline(opt_match.group(2))))
            i += 1
            continue

        ans_match = re.match(r'^Ответ[:\s]+(.+)', line, re.IGNORECASE)
        if ans_match:
            if in_options:
                html_parts.append('</div>')
                in_options = False
            html_parts.append('<p style="margin-top:8px;font-size:13px;color:#16a34a;font-weight:600">Correct: %s</p>' % _escape(ans_match.group(1)))
            html_parts.append('</div>')
            in_question = False
            i += 1
            continue

        html_parts.append('<p>%s</p>' % _format_inline(line))
        i += 1

    if in_options:
        html_parts.append('</div>')
    if in_question:
        html_parts.append('</div>')

    return '\n'.join(html_parts)


def format_resources(raw):
    if not raw or not raw.strip():
        return ""
    lines = raw.strip().split('\n')
    html_parts = ['<ul style="list-style:none;padding:0">']

    for line in lines:
        line = line.strip()
        if not line:
            continue
        url_match = re.search(r'(https?://\S+)', line)
        if url_match:
            url = url_match.group(1)
            text = line.replace(url, '').strip(' -:*')
            if not text:
                text = url
            html_parts.append('<li style="padding:8px 12px;margin-bottom:6px;border-radius:8px;border:1px solid #e2e8f0;background:#fafbfd"><a href="%s" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none;font-weight:500">%s</a></li>' % (_escape(url), _format_inline(text)))
        else:
            bullet = re.sub(r'^[\u2022\u2219\xB7\-\*\d\.\)]+\s*', '', line).strip()
            if bullet:
                html_parts.append('<li style="padding:8px 12px;margin-bottom:6px;border-radius:8px;border:1px solid #e2e8f0;background:#fafbfd">%s</li>' % _format_inline(bullet))

    html_parts.append('</ul>')
    return '\n'.join(html_parts)


def _escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _format_inline(text):
    t = _escape(text)
    # Bold text between special quotes
    t = re.sub(r'[\u00AB\u201C]([^\u00BB\u201D]+)[\u00BB\u201D]', r'<strong>\1</strong>', t)
    # Italic for parenthetical explanations (4-80 chars)
    t = re.sub(r'\(([^)]{4,80})\)', r'(<em>\1</em>)', t)
    # Code for backtick content
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return t


FORMATTERS = {
    'theory': format_theory,
    'practice': format_practice,
    'test': format_test,
    'resources': format_resources,
}


async def seed():
    await init_db()

    if not os.path.exists(BLOCKS_JSON):
        print("ERROR: %s not found" % BLOCKS_JSON)
        return

    with open(BLOCKS_JSON, "r", encoding="utf-8") as f:
        blocks = json.load(f)

    print("Loaded %d blocks from JSON" % len(blocks))

    async with async_session() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN).limit(1))
        admin = result.scalar_one_or_none()
        if not admin:
            print("ERROR: No admin user found.")
            return
        print("Using admin: %s" % admin.email)

        print("Deleting existing training data...")
        await db.execute(delete(topic_hashtags))
        await db.execute(delete(TopicProgress))
        await db.execute(delete(TrainingSubmission))
        await db.execute(delete(TrainingTask))
        await db.execute(delete(TrainingContent))
        await db.execute(delete(CourseAssignment))
        await db.execute(delete(TrainingTopic))
        await db.execute(delete(TrainingCourse))
        await db.execute(delete(Hashtag))
        await db.commit()
        print("Existing data deleted.")

        # ONE course
        course = TrainingCourse(
            title=COURSE_TITLE,
            description=COURSE_DESC,
            order=0,
            is_published=True,
            created_by=admin.id,
        )
        db.add(course)
        await db.flush()
        print("Created course: %s" % course.title)

        total_topics = 0
        total_content = 0
        topic_order = 0

        for block in blocks:
            bi = block["block_index"]
            block_section = BLOCK_NAMES.get(bi, "Block %d" % bi)
            print("\nProcessing: %s" % block_section)

            for topic in block["topics"]:
                section_title = "%s / %s" % (block_section, topic['title'])

                for subtopic in topic["subtopics"]:
                    t = TrainingTopic(
                        course_id=course.id,
                        title=subtopic["title"],
                        description=None,
                        order=topic_order,
                        section_title=section_title,
                        difficulty=None,
                    )
                    db.add(t)
                    await db.flush()
                    total_topics += 1

                    content_order = 0
                    for ct, ct_title in [
                        ("theory", "Theory"),
                        ("practice", "Practice"),
                        ("test", "Test"),
                        ("resources", "Resources"),
                    ]:
                        raw_body = subtopic.get(ct, "")
                        if raw_body and raw_body.strip():
                            formatter = FORMATTERS.get(ct, format_theory)
                            formatted_html = formatter(raw_body)
                            if formatted_html.strip():
                                cb = TrainingContent(
                                    topic_id=t.id,
                                    title=ct_title,
                                    body=formatted_html,
                                    content_type=ct,
                                    order=content_order,
                                )
                                db.add(cb)
                                total_content += 1
                                content_order += 1

                    topic_order += 1

        await db.commit()
        print("\n=== SEED COMPLETE ===")
        print("Course: %s" % COURSE_TITLE)
        print("Topics (subtopics): %d" % total_topics)
        print("Content blocks: %d" % total_content)


if __name__ == "__main__":
    asyncio.run(seed())
