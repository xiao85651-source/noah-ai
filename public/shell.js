const languages=['zh','en','ja','es','ar'];
const words={
 login:['登录','Sign in','ログイン','Iniciar sesión','تسجيل الدخول'],
 welcome:['欢迎来到 Noah','Welcome to Noah','Noah へようこそ','Te damos la bienvenida a Noah','مرحبا بك في نوح'],
 subtitle:['汇聚微光，承载新知。','An ark for shared intelligence.','小さな光を集め、新しい知へ。','Un arca para el conocimiento compartido.','فلك يجمع نور المعرفة.'],
 continue:['使用 Google 账号继续，或保留访客体验。','Continue with Google, or explore as a guest.','Google でログイン、またはゲストで続けます。','Continúa con Google o explora como visitante.','تابع باستخدام Google أو استكشف كضيف.'],
 connecting:['正在连接 Google…','Connecting to Google…','Google に接続中…','Conectando con Google…','جار الاتصال بـ Google…'],
 checking:['正在验证登录…','Verifying your sign-in…','ログインを確認中…','Verificando tu acceso…','جار التحقق من تسجيل الدخول…'],
 unavailable:['Google 登录暂不可用，请稍后重试。','Google sign-in is unavailable. Please try again shortly.','Google ログインを利用できません。後でもう一度お試しください。','El acceso con Google no está disponible. Inténtalo de nuevo.','تسجيل الدخول بـ Google غير متاح الآن. حاول لاحقا.'],
 expired:['登录已过期，请重新登录。','Your sign-in expired. Please sign in again.','ログインの有効期限が切れました。','Tu sesión ha caducado. Vuelve a iniciar sesión.','انتهت صلاحية الجلسة. سجل الدخول مجددا.'],
 guest:['继续访客体验','Continue as a guest','ゲストで続ける','Continuar como visitante','المتابعة كضيف'],
 retry:['重试','Try again','再試行','Reintentar','إعادة المحاولة'],
 notice:['仅用于识别登录身份。对话不会自动进入训练。','Used to identify your account. Chats are not automatically used for training.','アカウント識別のみに使用します。会話は自動で学習に使われません。','Solo para identificar tu cuenta. Los chats no se usan automáticamente para entrenar.','لتحديد هوية الحساب فقط. لا تستخدم المحادثات للتدريب تلقائيا.'],
 privacy:['隐私说明','Privacy','プライバシー','Privacidad','الخصوصية'],
 logout:['退出 Noah 登录','Sign out of Noah','Noah からログアウト','Cerrar sesión de Noah','تسجيل الخروج من نوح'],
 member:['普通用户','Member','一般ユーザー','Miembro','عضو'],
 replay:['重播开场','Replay introduction','イントロを再生','Repetir introducción','إعادة المقدمة'],
 skip:['跳过','Skip','スキップ','Omitir','تخطي'],
 enter:['进入工作空间','Enter workspace','ワークスペースへ','Entrar al espacio','دخول مساحة العمل'],
 close:['关闭','Close','閉じる','Cerrar','إغلاق']
};
const ark='<svg class="ark-scene" viewBox="0 0 240 166" fill="none" aria-hidden="true"><circle class="ark-sun" cx="160" cy="43" r="29"/><path class="ark-horizon" d="M24 118H216"/><g class="ark-boat"><path class="ark-hull" d="M59 91H181L163 119H89L59 91Z"/><path class="ark-cabin" d="M89 91V62L120 40L151 62V91"/><path class="ark-door" d="M109 91V68H131V91"/><path class="ark-window" d="M113 75H127V86H113Z"/><path class="ark-deck" d="M78 86H162"/></g><path class="ark-water water-one" d="M37 132C52 132 52 125 67 125S82 132 97 132S112 125 127 125S142 132 157 132S172 125 187 125S202 132 210 132"/><path class="ark-water water-two" d="M57 147C72 147 72 141 87 141S102 147 117 147S132 141 147 141S162 147 177 147"/><path class="ark-star" d="M179 24V36M173 30H185"/><circle class="ark-speck" cx="64" cy="50" r="2"/></svg>';
let initialized=false,authControl,member=null,sessionToken='',configPromise,sdkPromise,loginDialog;
function language(){let value=document.querySelector('#language')?.value;try{value=value||localStorage.getItem('noah-language');}catch{}return languages.includes(value)?value:'zh';}
function t(key){return words[key][languages.indexOf(language())];}
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function storeSession(value){sessionToken=value||'';try{if(value)sessionStorage.setItem('noah-member-session',value);else sessionStorage.removeItem('noah-member-session');}catch{}}
function savedSession(){try{return sessionStorage.getItem('noah-member-session')||'';}catch{return '';}}
async function apiOrigin(){
 if(!configPromise)configPromise=fetch('/auth-config.json',{cache:'no-store',credentials:'omit'}).then(r=>{if(!r.ok)throw Error('config');return r.json();}).then(config=>{
  const url=new URL(config.apiOrigin);const local=['localhost','127.0.0.1'].includes(url.hostname);
  if((url.protocol!=='https:'&&!(local&&url.protocol==='http:'))||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error('origin');
  return url.origin;
 }).catch(error=>{configPromise=null;throw error;});
 return configPromise;
}
async function api(path,options={}){
 const origin=await apiOrigin();const headers={};
 if(options.body!==undefined)headers['Content-Type']='application/json';
 if(options.token)headers.Authorization='Bearer '+options.token;
 const response=await fetch(origin+path,{method:options.body===undefined?'GET':'POST',headers,body:options.body===undefined?undefined:JSON.stringify(options.body),credentials:'omit',redirect:'error',signal:AbortSignal.timeout(20000)});
 const result=response.status===204?{}:await response.json();
 if(!response.ok){const error=Error(result.error||'request');error.status=response.status;throw error;}
 return result;
}
function updateAccount(){
 if(!authControl)return;authControl.replaceChildren();
 if(!member){const button=element('button','noah-login-button',t('login'));button.type='button';button.id='noah-sign-in';button.addEventListener('click',openLogin);authControl.append(button);return;}
 const details=element('details','noah-account');const summary=element('summary','noah-account-summary');
 summary.append(element('span','noah-account-avatar',Array.from(member.name||'N')[0]),element('span','noah-account-name',member.name));details.append(summary);
 const panel=element('div','noah-account-panel');panel.append(element('strong','',member.name),element('span','noah-account-email',member.email),element('span','noah-member-role',t('member')));
 const out=element('button','noah-sign-out',t('logout'));out.type='button';out.addEventListener('click',async()=>{const previous=sessionToken;storeSession('');member=null;updateAccount();try{await api('/api/auth/logout',{token:previous,body:{}});}catch{}globalThis.google?.accounts?.id?.disableAutoSelect();});
 panel.append(out);details.append(panel);authControl.append(details);
}
function loadGoogle(){
 if(globalThis.google?.accounts?.id)return Promise.resolve();
 if(!sdkPromise)sdkPromise=new Promise((resolve,reject)=>{
  const script=document.createElement('script');script.src='https://accounts.google.com/gsi/client?hl='+({zh:'zh-CN',en:'en',ja:'ja',es:'es',ar:'ar'}[language()]);script.async=true;script.defer=true;
  const timer=setTimeout(()=>reject(Error('google_timeout')),20000);
  script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);reject(Error('google_load'));};document.head.append(script);
 }).catch(error=>{sdkPromise=null;throw error;});
 return sdkPromise;
}
async function prepareGoogle(dialog){
 const status=dialog.querySelector('.noah-auth-status'),slot=dialog.querySelector('.noah-google-button'),retry=dialog.querySelector('.noah-auth-retry');
 slot.replaceChildren();status.textContent=t('connecting');retry.hidden=true;
 try{
  const config=await api('/api/auth/config');if(!config.enabled||!config.clientId)throw Error('not_ready');
  const challenge=await api('/api/auth/challenge');await loadGoogle();if(!dialog.open)return;
  globalThis.google.accounts.id.initialize({client_id:config.clientId,nonce:challenge.nonce,auto_select:false,ux_mode:'popup',use_fedcm_for_button:false,callback:async result=>{
   if(!dialog.open)return;status.textContent=t('checking');
   try{
    const session=await api('/api/auth/google',{body:{credential:result.credential,nonce:challenge.nonce}});
    if(!dialog.open)return;storeSession(session.token);member=session.user;updateAccount();dialog.close();
   }catch(error){status.textContent=t(error.message==='login_expired'?'expired':'unavailable');retry.hidden=false;}
  }});
  globalThis.google.accounts.id.renderButton(slot,{type:'standard',theme:'outline',size:'large',shape:'pill',text:'continue_with',width:Math.min(320,dialog.clientWidth-64),locale:{zh:'zh-CN',en:'en',ja:'ja',es:'es',ar:'ar'}[language()]});
  status.textContent='';
 }catch{if(dialog.open){status.textContent=t('unavailable');retry.hidden=false;}}
}
function openLogin(){
 if(loginDialog?.open)return;const dialog=element('dialog','noah-auth');loginDialog=dialog;
 dialog.setAttribute('aria-labelledby','noah-auth-title');
 const close=element('button','noah-auth-close','×');close.type='button';close.setAttribute('aria-label',t('close'));close.addEventListener('click',()=>dialog.close());
 const image=element('img','noah-auth-mark');image.src='/mark.svg';image.alt='';image.width=48;image.height=48;
 const heading=element('h2','',t('welcome'));heading.id='noah-auth-title';
 const slot=element('div','noah-google-button'),status=element('p','noah-auth-status');status.setAttribute('role','status');
 const retry=element('button','secondary noah-auth-retry',t('retry'));retry.type='button';retry.hidden=true;retry.addEventListener('click',()=>prepareGoogle(dialog));
 const guest=element('button','noah-guest-button',t('guest'));guest.type='button';guest.addEventListener('click',()=>dialog.close());
 const privacy=element('a','',t('privacy'));privacy.href='/privacy.html';
 dialog.append(close,image,heading,element('p','noah-auth-description',t('continue')),slot,status,retry,guest,element('p','noah-auth-notice',t('notice')),privacy);
 dialog.addEventListener('close',()=>{dialog.remove();loginDialog=null;document.querySelector('#noah-sign-in')?.focus();});document.body.append(dialog);dialog.showModal();prepareGoogle(dialog);
}
export function showArkIntroduction(hold=false){
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(document.querySelector('.noah-intro')||(!hold&&reduced))return;
 if(!hold){try{if(sessionStorage.getItem('noah-intro-v1'))return;sessionStorage.setItem('noah-intro-v1','1');}catch{}}
 const dialog=element('dialog','noah-intro');dialog.setAttribute('aria-label','Noah');
 const scene=element('div','noah-intro-content');scene.innerHTML=ark;
 scene.append(element('p','noah-intro-wordmark','Noah'),element('p','noah-intro-subtitle',t('subtitle')),element('span','noah-intro-caption','ZENITHSMART · NOAH'));
 const skip=element('button','noah-intro-skip',t(hold?'enter':'skip'));skip.type='button';skip.addEventListener('click',()=>dialog.close());
 dialog.append(scene,skip);let timer;dialog.addEventListener('close',()=>{clearTimeout(timer);dialog.remove();},{once:true});document.body.append(dialog);dialog.showModal();
 if(!hold)timer=setTimeout(()=>dialog.close(),1950);
}
export function startNoahShell({signIn=false}={}){
 if(initialized)return;initialized=true;
 const footer=document.querySelector('footer');
 if(footer){const links=element('span','noah-footer-links');const replay=element('button','noah-replay',t('replay'));replay.type='button';replay.addEventListener('click',()=>showArkIntroduction(true));const privacy=element('a','noah-privacy-link',t('privacy'));privacy.href='/privacy.html';links.append(replay,privacy);footer.append(links);}
 if(signIn){authControl=element('div','noah-auth-control');(document.querySelector('.header-right')||document.querySelector('header'))?.append(authControl);updateAccount();const previous=savedSession();
  if(previous&&previous.length<=200){sessionToken=previous;api('/api/auth/me',{token:previous}).then(result=>{member=result.user;updateAccount();}).catch(error=>{if(error.status===401)storeSession('');});}
 }
 document.addEventListener('change',event=>{if(event.target.id==='language'){updateAccount();const replay=document.querySelector('.noah-replay'),privacy=document.querySelector('.noah-privacy-link');if(replay)replay.textContent=t('replay');if(privacy)privacy.textContent=t('privacy');}});
 showArkIntroduction();
}
