const sessionId=new URL(location.href).searchParams.get('sessionId')||null;
globalThis.philharmonieTransport=async(path,body)=>{
  const response=await fetch(new URL('request',import.meta.url),{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:body?'POST':'GET',path,body,sessionId})});
  const data=await response.json();if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);return data;
};
await import('./app.mjs');
