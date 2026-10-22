/* Native app downloads shared by the login and authenticated sidebar. */
'use strict';
const NJA_NATIVE_DOWNLOADS={
 windows:'https://github.com/njamarketing/nja-system/releases/latest/download/NJA-System-Windows.exe',
 android:'https://github.com/njamarketing/nja-system/releases/latest/download/NJA-System-Android.apk'
};
function nativePlatformIcon(platform){return platform==='windows'?`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4.5 10.5 3v8H3zm8.5-1.7L21 1v10h-9.5zM3 12h7.5v8L3 18.5zm8.5 0H21v10l-9.5-1.8z" fill="currentColor"/></svg>`:`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7.1 7.2-1.7-3a.7.7 0 0 1 1.2-.7l1.8 3A9 9 0 0 1 12 5.8c1.3 0 2.5.2 3.6.7l1.8-3a.7.7 0 0 1 1.2.7l-1.7 3A7.2 7.2 0 0 1 20 13H4a7.2 7.2 0 0 1 3.1-5.8ZM8.5 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm7 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM4 14h16v5.5A1.5 1.5 0 0 1 18.5 21h-1v2h-2v-2h-7v2h-2v-2h-1A1.5 1.5 0 0 1 4 19.5Z" fill="currentColor"/></svg>`}
function nativeDownloadsMarkup(context='login'){
 const compact=context==='sidebar';
 return `<div class="native-downloads ${compact?'is-compact':''}"><div class="native-download-heading"><strong>${compact?'Baixar aplicativo':'Leve o NJA com você'}</strong>${compact?'':`<span>Escolha a versão do seu dispositivo</span>`}</div><div class="native-download-actions"><a href="${NJA_NATIVE_DOWNLOADS.windows}" class="native-download windows" target="_blank" rel="noopener" download>${nativePlatformIcon('windows')}<span><small>Baixar para</small><b>Windows</b></span><em>.exe</em></a><a href="${NJA_NATIVE_DOWNLOADS.android}" class="native-download android" target="_blank" rel="noopener" download>${nativePlatformIcon('android')}<span><small>Baixar para</small><b>Android</b></span><em>.apk</em></a></div></div>`;
}
const nativeLoginScreen=loginScreen;
loginScreen=function(mode='login'){
 nativeLoginScreen(mode);
 const reset=new URLSearchParams(location.search).get('reset');if(reset||mode!=='login')return;
 const access=document.querySelector('.login-access'),card=document.querySelector('.login-card');if(!access||!card||access.querySelector('.native-downloads'))return;
 card.insertAdjacentHTML('afterend',nativeDownloadsMarkup('login'));
 const note=access.querySelector('.login-mobile-note');if(note)note.textContent='Também disponível como aplicativo para Windows e Android.';
};
const nativeShell=shell;
shell=function(){nativeShell();const banner=document.querySelector('.mini-banner');if(banner)banner.innerHTML=nativeDownloadsMarkup('sidebar')};
installModal=function(){modal('Aplicativos NJA System',`${nativeDownloadsMarkup('modal')}<hr class="splitline"><h3>Instalação pelo navegador</h3><p>No iPhone, abra pelo Safari, toque em Compartilhar → “Adicionar à Tela de Início”. No Android e no computador, você também pode instalar a versão PWA pelo navegador.</p>${installPrompt?'<button class="btn lime" id="install-now">Instalar versão do navegador</button>':''}<p class="tiny muted">Os aplicativos usam o ambiente seguro do NJA System e precisam de conexão com a internet. Câmera e microfone serão solicitados somente ao iniciar chamadas.</p>`);document.querySelector('#install-now')?.addEventListener('click',async()=>{await installPrompt.prompt();installPrompt=null;closeModal()})};
