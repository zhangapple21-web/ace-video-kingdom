import re
with open('tmpaf2pn2y7.html', 'r', encoding='utf-8') as f:
    html = f.read()
text = re.sub(r'<[^>]+>', '', html)
text = re.sub(r'\s+', '', text)
print('Text length (chars):', len(text))
visual_indicators = ['光','色','亮','暗','影','红','白','灰','黑','手','脚','眼','指','脸','口','肩','身','步','声','响','动','停','推','拉','摸','碰','看','见','站','坐','走','进','出','开','合']
sentences = re.split(r'[。！？]', text)
visual_count = sum(1 for s in sentences if any(v in s for v in visual_indicators) and len(s) > 10)
print('Estimated visual points:', visual_count)
banned = ['电影感推进', '自然微动作', 'PENDING_', 'TODO', 'FIXME']
for b in banned:
    if b in html:
        print('BANNED WORD FOUND:', b)
ai_patterns = ['显然', '事实上', '毫无疑问', '众所周知', '紧接着', '与此同时', '随即', '原来', '这就是', '目光中闪过一丝', '嘴角勾起一抹']
for p in ai_patterns:
    if p in html:
        print('AI PATTERN:', p)