import {translations,locales} from './i18n.js';
import {infer} from './transport.js';
import {startNoahShell} from './shell.js';
startNoahShell({signIn:true});
const $=s=>document.querySelector(s);
let language='zh',busy=false,paused=false;
try{language=localStorage.getItem('noah-language')||'zh';paused=localStorage.getItem('noah-companion-paused')==='1';}catch{}
if(!locales.includes(language))language='zh';
const t=key=>translations[language][key]??key;
const errors={zh:['请求较多，请稍后再试。','Noah 正忙，请稍后再试。'],en:['Too many requests. Please try again shortly.','Noah is busy. Please try again shortly.'],ja:['リクエストが多すぎます。しばらくしてからお試しください。','Noah は処理中です。しばらくしてからお試しください。'],es:['Demasiadas solicitudes. Inténtalo de nuevo más tarde.','Noah está ocupado. Inténtalo de nuevo más tarde.'],ar:['طلبات كثيرة. يرجى المحاولة لاحقًا.','نوح مشغول. يرجى المحاولة لاحقًا.']};
function translate(){
 document.documentElement.lang=language==='zh'?'zh-CN':language;document.documentElement.dir=language==='ar'?'rtl':'ltr';
 document.title='Noah · '+t('hello');$('#language').value=language;
 document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));
 document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>el.placeholder=t(el.dataset.i18nPlaceholder));
 $('#companion-status').textContent=t(busy?'companionThinking':'companionIdle');
}
$('#language').addEventListener('change',e=>{language=e.target.value;try{localStorage.setItem('noah-language',language);}catch{}translate();});
function message(role,text){const el=document.createElement('div');el.className='message '+role;const label=document.createElement('span');label.className='role';label.textContent=role==='user'?t('you'):'Noah · '+t('experimental');el.append(label,document.createTextNode(text));$('#messages').append(el);el.scrollIntoView({block:'end',behavior:'smooth'});return el;}
async function send(){
 const text=$('#prompt').value.trim();if(busy||!text)return;
 busy=true;$('#send').disabled=true;$('#welcome').hidden=true;$('#prompt').value='';message('user',text);
 const pending=message('assistant',t('generating'));$('#companion-status').textContent=t('companionThinking');
 try{
  const result=await infer(text,language);pending.lastChild.textContent=result.text;
 }catch(error){pending.lastChild.textContent=error.status===429?errors[language][0]:error.status===503?errors[language][1]:t('connectionError');pending.classList.add('error');}
 finally{busy=false;$('#send').disabled=false;$('#companion-status').textContent=t('companionIdle');}
}
$('#chat-form').addEventListener('submit',event=>{event.preventDefault();send();});
$('#prompt').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();send();}});
$('#new-chat').addEventListener('click',()=>{if(busy)return;$('#messages').replaceChildren();$('#welcome').hidden=false;$('#prompt').focus();});
$('#companion').classList.toggle('paused',paused);$('#companion-pause').setAttribute('aria-pressed',String(paused));$('#companion-pause').textContent=paused?'▷':'Ⅱ';
$('#companion-toggle').addEventListener('click',()=>{const collapsed=$('#companion').classList.toggle('is-collapsed');$('#companion-toggle').setAttribute('aria-expanded',String(!collapsed));$('#companion-chevron').textContent=collapsed?'⌃':'⌄';});
$('#companion-pause').addEventListener('click',()=>{paused=!paused;$('#companion').classList.toggle('paused',paused);$('#companion-pause').setAttribute('aria-pressed',String(paused));$('#companion-pause').textContent=paused?'▷':'Ⅱ';try{localStorage.setItem('noah-companion-paused',paused?'1':'0');}catch{}});
let greeting;
$('#companion-greet').addEventListener('click',()=>{$('#companion').classList.add('greet');$('#companion-status').textContent=t('companionHello');clearTimeout(greeting);greeting=setTimeout(()=>{$('#companion').classList.remove('greet');$('#companion-status').textContent=t(busy?'companionThinking':'companionIdle');},3000);});
translate();
