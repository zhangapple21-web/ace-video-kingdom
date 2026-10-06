const ORIGIN = "https://tinghe-archive.pages.dev";

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    if (!incoming.pathname.startsWith("/dramai")) {
      return fetch(request);
    }

    const upstream = new URL(ORIGIN);
    const suffix = incoming.pathname.slice("/dramai".length);
    upstream.pathname = suffix || "/";
    upstream.search = incoming.search;

    const response = await fetch(new Request(upstream, request));
    const headers = new Headers(response.headers);
    headers.set("x-tinghe-route", "pages-proxy");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
