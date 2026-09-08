// Server-side only — this env var must NOT have the NEXT_PUBLIC_ prefix.
const GITHUB_PAT = process.env.GITHUB_PAT;
const OWNER = "unloan83";
const REPO = "dualengine";

export default async function handler(req, res) {
  const url = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/paper_trade_log.csv`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${GITHUB_PAT}` } });
  if (!r.ok) return res.status(502).json({ error: "Failed to fetch log" });
  const csvText = await r.text();
  res.status(200).send(csvText);
}
