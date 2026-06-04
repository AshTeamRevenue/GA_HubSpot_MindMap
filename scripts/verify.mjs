import fs from "node:fs";
import vm from "node:vm";

const indexHtml = fs.readFileSync("index.html", "utf8");
const dataJs = fs.readFileSync("data.js", "utf8");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const inlineScripts = [...indexHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
inlineScripts.forEach((script, index) => {
  try {
    new Function(script);
  } catch (error) {
    throw new Error(`Inline script ${index + 1} does not compile: ${error.message}`);
  }
});

const data = vm.runInNewContext(`${dataJs}; ({ sheetData, lastSynced, semanticDictionary, libraryMetadata: typeof libraryMetadata === "undefined" ? null : libraryMetadata });`);
const articleRows = data.sheetData.trim().split(/\n(?=[^,\n]+,)/).slice(1);

assert(indexHtml.includes("data.js?v=total-mastery-20260604"), "index.html is not cache-busting the June 4 data file.");
assert(indexHtml.includes("Click any node to explore."), "Instruction bar copy is missing.");
assert(indexHtml.includes("Click a leaf node to open the HubSpot article."), "Leaf-node instruction copy is missing.");
assert(indexHtml.includes("Email & Campaigns"), "User-facing Email & Campaigns bucket is missing.");
assert(indexHtml.includes("Lists & Lead Routing"), "User-facing Lists & Lead Routing bucket is missing.");
assert(indexHtml.includes("Deals & Pipeline"), "User-facing Deals & Pipeline bucket is missing.");
assert(indexHtml.includes("Help Desk & Support"), "User-facing Help Desk & Support bucket is missing.");
assert(indexHtml.includes("applyCompactSearchLayout"), "Compact search layout helper is missing.");
assert(indexHtml.includes("zoom-in-btn") && indexHtml.includes("zoom-out-btn") && indexHtml.includes("recenter-btn"), "Map zoom/recenter controls are missing.");

assert(data.lastSynced === "June 04, 2026", `Unexpected lastSynced value: ${data.lastSynced}`);
assert(articleRows.length >= 599, `Expected at least 599 article rows, found ${articleRows.length}.`);
[
  "Deals",
  "Sequences",
  "Workflows",
  "Conversations",
  "Help Desk",
  "Breeze"
].forEach(label => {
  assert(data.sheetData.includes(label), `data.js is missing expected content: ${label}`);
});

console.log(`Verified ${inlineScripts.length} inline script(s).`);
console.log(`Verified ${articleRows.length} article rows synced on ${data.lastSynced}.`);
