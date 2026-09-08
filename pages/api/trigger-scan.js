const GITHUB_PAT = process.env.GITHUB_PAT; // server-side only
const OWNER = "unloan83";
const REPO = "dualengine";
const WORKFLOW_FILE = "trading_bot.yml"; // your workflow file name under .github/workflows

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();
  const { velocity, atr_mult } = req.body;

  const r = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${GITHUB_PAT}`,
      },
      body: JSON.stringify({
        ref: "main",
        inputs: { velocity: String(velocity), atr_mult: String(atr_mult) },
      }),
    }
  );
  if (r.status === 204) return res.status(200).json({ ok: true });
  return res.status(502).json({ error: "Dispatch failed" });
}
