import assert from "node:assert/strict";
import worker from "../www/worker.js";

const r = await worker.fetch(new Request("https://www.secureaiarch.com/tr/patterns/structured-output?x=1"));
assert.equal(r.status, 301);
assert.equal(r.headers.get("location"), "https://secureaiarch.com/tr/patterns/structured-output?x=1");
assert.equal((await worker.fetch(new Request("https://secureaiarch.com/"))).status, 404);
console.log("ok: www redirect");
