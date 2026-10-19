// Redirects www.<apex> to the apex with a 301, keeping the path and query.
// Kept in this repo so the product can be moved to another account on its own.
export default {
  fetch(request) {
    const url = new URL(request.url);
    if (!url.hostname.startsWith("www.")) return new Response("Not found", { status: 404 });
    url.hostname = url.hostname.slice(4);
    return Response.redirect(url.toString(), 301);
  },
};
