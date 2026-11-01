import {translations,locales} from './i18n.js';
import {startNoahShell} from './shell.js';
const $=selector=>document.querySelector(selector);
let language='zh',metadata=null,failed=false;
try{language=new URLSearchParams(location.search).get('lang')||localStorage.getItem('noah-language')||'zh';}catch{}
if(!locales.includes(language))language='zh';
const t=key=>translations[language][key]??key;
function translate(){
 document.documentElement.lang=language==='zh'?'zh-CN':language;
 document.documentElement.dir=language==='ar'?'rtl':'ltr';
 document.title='Noah · '+t('network');$('#language').value=language;
 document.querySelectorAll('[data-i18n]').forEach(node=>node.textContent=t(node.dataset.i18n));
 if(metadata){$('#published-step').textContent=metadata.step.toLocaleString(language);$('#published-parameters').textContent=metadata.parameters.toLocaleString(language);}
 $('#metadata-status').textContent=failed?t('loadMetadataError'):'';
}
$('#language').addEventListener('change',event=>{language=event.target.value;try{localStorage.setItem('noah-language',language);}catch{}translate();});
translate();
startNoahShell({signIn:true});
try{
 const runtime=await fetch('/runtime.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw Error('Runtime unavailable');return response.json();});
 const response=await fetch(runtime.mode==='browser'?'/noah-web.json':'/api/info',{cache:'no-store'});
 if(!response.ok)throw Error('Model metadata unavailable');
 const value=await response.json();
 if(!Number.isSafeInteger(value.step)||value.step<0||!Number.isSafeInteger(value.parameters)||value.parameters<=0)throw Error('Invalid model metadata');
 metadata={step:value.step,parameters:value.parameters};
}catch{failed=true;}
translate();

$('#copy-project').addEventListener('click',async()=>{
 const url=new URL('https://zenithsmart.xin/train.html');url.searchParams.set('lang',language);
 const link=document.querySelector('.project-url');link.href=url.href;link.textContent=url.href;
 try{await navigator.clipboard.writeText(url.href);$('#share-status').textContent=t('copiedProjectLink');}
 catch{$('#share-status').textContent=t('copyProjectManual');link.focus();}
});
