#!/usr/bin/env python3
"""Convert a 2018 Blogger Takeout feed.atom into a WordPress WXR (1.2) file.

Handts POST/PAGE/COMMENT entries, preserves permalink slugs from
<blogger:filename>, labels -> tags, and threads comments to their parent post.
"""
import sys, html, xml.etree.ElementTree as ET
from datetime import datetime, timezone

ATOM='http://www.w3.org/2005/Atom'
BLOG='http://schemas.google.com/blogger/2018'
ns={'a':ATOM,'b':BLOG}

SITE_URL='https://dharmabruce.com'
AUTHOR_LOGIN='dharmabruce'
AUTHOR_NAME='dharmabruce'
AUTHOR_EMAIL='dharmabruce@gmail.com'
ATTIC_CATEGORY='Attic'   # group all migrated Blogger posts under one section

src=sys.argv[1]
out=sys.argv[2]
root=ET.parse(src).getroot()

def txt(e, path):
    n=e.find(path, ns)
    return n.text if (n is not None and n.text) else ''

def parse_dt(s):
    # Blogger uses ...Z or with offset; normalize to UTC
    s=s.strip()
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
    except ValueError:
        d=datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def post_id_num(full_id):
    # tag:blogger.com,1999:blog-29764489.post-62514098219917728 -> 62514098219917728
    return full_id.rsplit('.post-',1)[-1]

def slug_from_filename(fn):
    # /2008/07/dark-knight-at-imax.html -> dark-knight-at-imax
    base=fn.rsplit('/',1)[-1]
    if base.endswith('.html'): base=base[:-5]
    return base

posts=[]      # dicts
comments_by_parent={}  # parent_post_num -> [comment dicts]

for e in root.findall('a:entry', ns):
    btype=txt(e,'b:type')
    status=txt(e,'b:status')
    if btype=='COMMENT':
        parent=e.find('b:parent', ns)
        if parent is None or not parent.text: continue
        pnum=post_id_num(parent.text)
        comments_by_parent.setdefault(pnum,[]).append({
            'author': txt(e,'a:author/a:name') or 'Anonymous',
            'email': txt(e,'a:author/a:email'),
            'uri': txt(e,'a:author/a:uri'),
            'content': txt(e,'a:content'),
            'date': parse_dt(txt(e,'a:published')),
            'approved': '1' if status=='LIVE' else '0',
        })
    elif btype in ('POST','PAGE'):
        fn=txt(e,'b:filename')
        posts.append({
            'num': post_id_num(txt(e,'a:id')),
            'type': 'page' if btype=='PAGE' else 'post',
            'title': txt(e,'a:title') or '(untitled)',
            'content': txt(e,'a:content'),
            'date': parse_dt(txt(e,'a:published')),
            'status': 'publish' if status=='LIVE' else 'draft',
            'slug': slug_from_filename(fn) if fn else '',
            'filename': fn,
            'labels': [c.get('term') for c in e.findall('a:category', ns) if c.get('term')],
        })

def cd(s):  # CDATA wrap
    return '<![CDATA['+ (s or '').replace(']]>',']]]]><![CDATA[>') +']]>'

def esc(s):
    return html.escape(s or '', quote=False)

def wxr_date(d):       # Sat, 26 Jul 2008 ... +0000 (RFC822-ish, pubDate)
    return d.strftime('%a, %d %b %Y %H:%M:%S +0000')
def wp_date(d):        # 2008-07-26 19:00:00
    return d.strftime('%Y-%m-%d %H:%M:%S')

lines=[]
lines.append('<?xml version="1.0" encoding="UTF-8"?>')
lines.append('<rss version="2.0"')
lines.append('  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"')
lines.append('  xmlns:content="http://purl.org/rss/1.0/modules/content/"')
lines.append('  xmlns:wfw="http://wellformedweb.org/CommentAPI/"')
lines.append('  xmlns:dc="http://purl.org/dc/elements/1.1/"')
lines.append('  xmlns:wp="http://wordpress.org/export/1.2/">')
lines.append('<channel>')
lines.append(f'  <title>dharmabruce\'s Journal</title>')
lines.append(f'  <link>{SITE_URL}</link>')
lines.append('  <description>Migrated from Blogger (dharmabruce.blogspot.com)</description>')
lines.append('  <language>en-US</language>')
lines.append('  <wp:wxr_version>1.2</wp:wxr_version>')
lines.append(f'  <wp:base_site_url>{SITE_URL}</wp:base_site_url>')
lines.append(f'  <wp:base_blog_url>{SITE_URL}</wp:base_blog_url>')
lines.append('  <wp:author>')
lines.append('    <wp:author_id>1</wp:author_id>')
lines.append(f'    <wp:author_login>{cd(AUTHOR_LOGIN)}</wp:author_login>')
lines.append(f'    <wp:author_email>{esc(AUTHOR_EMAIL)}</wp:author_email>')
lines.append(f'    <wp:author_display_name>{cd(AUTHOR_NAME)}</wp:author_display_name>')
lines.append('  </wp:author>')

for p in posts:
    permalink = f"{SITE_URL}{p['filename']}" if p['filename'] else SITE_URL
    lines.append('  <item>')
    lines.append(f"    <title>{esc(p['title'])}</title>")
    lines.append(f"    <link>{esc(permalink)}</link>")
    lines.append(f"    <pubDate>{wxr_date(p['date'])}</pubDate>")
    lines.append(f"    <dc:creator>{cd(AUTHOR_LOGIN)}</dc:creator>")
    lines.append(f"    <content:encoded>{cd(p['content'])}</content:encoded>")
    lines.append('    <excerpt:encoded><![CDATA[]]></excerpt:encoded>')
    lines.append(f"    <wp:post_id>{p['num']}</wp:post_id>")
    lines.append(f"    <wp:post_date>{cd(wp_date(p['date']))}</wp:post_date>")
    lines.append(f"    <wp:post_date_gmt>{cd(wp_date(p['date']))}</wp:post_date_gmt>")
    lines.append('    <wp:comment_status><![CDATA[open]]></wp:comment_status>')
    lines.append('    <wp:ping_status><![CDATA[closed]]></wp:ping_status>')
    lines.append(f"    <wp:post_name>{cd(p['slug'])}</wp:post_name>")
    lines.append(f"    <wp:status>{cd(p['status'])}</wp:status>")
    lines.append('    <wp:post_parent>0</wp:post_parent>')
    lines.append('    <wp:menu_order>0</wp:menu_order>')
    lines.append(f"    <wp:post_type>{cd(p['type'])}</wp:post_type>")
    lines.append('    <wp:is_sticky>0</wp:is_sticky>')
    lines.append(f'    <category domain="category" nicename="{ATTIC_CATEGORY.lower()}">{cd(ATTIC_CATEGORY)}</category>')
    for lbl in p['labels']:
        lines.append(f'    <category domain="post_tag" nicename="{esc(lbl.lower().replace(" ","-"))}">{cd(lbl)}</category>')
    for i,c in enumerate(comments_by_parent.get(p['num'],[]),1):
        lines.append('    <wp:comment>')
        lines.append(f'      <wp:comment_id>{i}</wp:comment_id>')
        lines.append(f"      <wp:comment_author>{cd(c['author'])}</wp:comment_author>")
        lines.append(f"      <wp:comment_author_email>{esc(c['email'])}</wp:comment_author_email>")
        lines.append(f"      <wp:comment_author_url>{esc(c['uri'])}</wp:comment_author_url>")
        lines.append(f"      <wp:comment_date>{cd(wp_date(c['date']))}</wp:comment_date>")
        lines.append(f"      <wp:comment_date_gmt>{cd(wp_date(c['date']))}</wp:comment_date_gmt>")
        lines.append(f"      <wp:comment_content>{cd(c['content'])}</wp:comment_content>")
        lines.append(f"      <wp:comment_approved>{cd(c['approved'])}</wp:comment_approved>")
        lines.append('      <wp:comment_type><![CDATA[comment]]></wp:comment_type>')
        lines.append('    </wp:comment>')
    lines.append('  </item>')

lines.append('</channel>')
lines.append('</rss>')

with open(out,'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))

pub=sum(1 for p in posts if p['status']=='publish')
draft=sum(1 for p in posts if p['status']=='draft')
ncom=sum(len(v) for v in comments_by_parent.values())
print(f"wrote {out}")
print(f"posts: {len(posts)} ({pub} publish / {draft} draft), comments: {ncom}")
print(f"posts without slug (drafts): {[p['title'] for p in posts if not p['slug']]}")
