"""List the public Machina corpus bucket into a TSV manifest: key<TAB>size<TAB>etag."""
import sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
BASE = "https://machina-deid-v1-challenge.s3.us-west-2.amazonaws.com/"
PREFIX = "releases/v1/corpus/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
out = open(sys.argv[1], "w")
token, n, total = None, 0, 0
while True:
    q = {"list-type": "2", "prefix": PREFIX, "max-keys": "1000"}
    if token: q["continuation-token"] = token
    root = ET.fromstring(urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(q), timeout=60).read())
    for c in root.findall("s:Contents", NS):
        key = c.find("s:Key", NS).text; size = int(c.find("s:Size", NS).text)
        out.write(f"{key[len(PREFIX):]}\t{size}\t{c.find('s:ETag', NS).text.strip(chr(34))}\n")
        n += 1; total += size
    if root.find("s:IsTruncated", NS).text != "true": break
    token = root.find("s:NextContinuationToken", NS).text
print(f"{n} files, {total/1e9:.1f} GB", file=sys.stderr)
