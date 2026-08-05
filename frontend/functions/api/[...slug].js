export async function onRequest(context) {
    const { request, env } = context;
    const UPSTREAM = env.UPSTREAM_API || 'https://peekorobo-db-bec52087b7e6.herokuapp.com';
    const PRIVATE_KEY = env.PRIVATE_API_KEY;
  
    const url = new URL(request.url);
    const upstreamPath = url.pathname.replace(/^\/api/, '') || '/';
    const upstreamUrl = UPSTREAM + upstreamPath + url.search;
  
    // Build headers: forward Authorization, Accept, Content-Type; never forward client X-API-Key
    const headers = new Headers(request.headers);
    headers.delete('x-api-key');
    if (!headers.get('authorization') && PRIVATE_KEY) {
      headers.set('X-API-Key', PRIVATE_KEY);
    }
  
    // Remove hop-by-hop headers that can cause issues
    ['connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailers','transfer-encoding','upgrade'].forEach(h => headers.delete(h));
  
    const upstreamReq = new Request(upstreamUrl, {
      method: request.method,
      headers,
      body: ['GET','HEAD'].includes(request.method) ? undefined : request.body,
      redirect: 'manual'
    });
  
    const resp = await fetch(upstreamReq);
    // Optionally strip any headers you don't want to expose (e.g., server internals)
    const respHeaders = new Headers(resp.headers);
    return new Response(resp.body, { status: resp.status, headers: respHeaders });
  }