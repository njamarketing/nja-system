/* Motion compensated in-between images. Runs away from the UI thread. */
'use strict';
const frames=new Map(),flows=new Map();let width=160,height=160;
function gray(a){const g=new Float32Array(width*height);for(let i=0;i<g.length;i++){let j=i*4;g[i]=(a[j]*.21+a[j+1]*.72+a[j+2]*.07)*a[j+3]/255;}return g;}
function field(a,b){const step=10,cols=Math.ceil(width/step)+1,rows=Math.ceil(height/step)+1,out=new Float32Array(cols*rows*2),ga=gray(a),gb=gray(b);
 for(let gy=0;gy<rows;gy++)for(let gx=0;gx<cols;gx++){const x=Math.min(width-5,Math.max(4,gx*step)),y=Math.min(height-5,Math.max(4,gy*step));let best=Infinity,bx=0,by=0;
  for(let dy=-8;dy<=8;dy+=2)for(let dx=-8;dx<=8;dx+=2){if(x+dx<4||x+dx>=width-4||y+dy<4||y+dy>=height-4)continue;let score=(dx*dx+dy*dy)*.18;
   for(let py=-4;py<=4;py+=2)for(let px=-4;px<=4;px+=2){const i=(y+py)*width+x+px,j=(y+py+dy)*width+x+px+dx;score+=Math.abs(ga[i]-gb[j])+Math.abs(a[i*4+3]-b[j*4+3])*.6;}
   if(score<best){best=score;bx=dx;by=dy;}
  }const k=(gy*cols+gx)*2;out[k]=bx;out[k+1]=by;
 }return {out,cols,rows,step};}
function vector(f,x,y){const gx=x/f.step,gy=y/f.step,ix=Math.min(f.cols-2,Math.floor(gx)),iy=Math.min(f.rows-2,Math.floor(gy)),tx=gx-ix,ty=gy-iy;let dx=0,dy=0;for(let yy=0;yy<2;yy++)for(let xx=0;xx<2;xx++){const w=(xx?tx:1-tx)*(yy?ty:1-ty),k=((iy+yy)*f.cols+ix+xx)*2;dx+=f.out[k]*w;dy+=f.out[k+1]*w;}return [dx,dy];}
function pixel(a,x,y,c){x=Math.max(0,Math.min(width-1.001,x));y=Math.max(0,Math.min(height-1.001,y));const ix=Math.floor(x),iy=Math.floor(y),tx=x-ix,ty=y-iy;return a[(iy*width+ix)*4+c]*(1-tx)*(1-ty)+a[(iy*width+ix+1)*4+c]*tx*(1-ty)+a[((iy+1)*width+ix)*4+c]*(1-tx)*ty+a[((iy+1)*width+ix+1)*4+c]*tx*ty;}
function interpolate(a,b,t,ab,ba){const out=new Uint8ClampedArray(a.length);for(let y=0;y<height;y++)for(let x=0;x<width;x++){const [dx,dy]=vector(ab,x,y),[ex,ey]=vector(ba,x,y),ax=x-dx*t,ay=y-dy*t,bx=x-ex*(1-t),by=y-ey*(1-t),aa=pixel(a,ax,ay,3),bb=pixel(b,bx,by,3),alpha=aa*(1-t)+bb*t,k=(y*width+x)*4;out[k+3]=alpha;for(let c=0;c<3;c++)out[k+c]=alpha?(pixel(a,ax,ay,c)*aa*(1-t)+pixel(b,bx,by,c)*bb*t)/alpha:0;}return out;}
onmessage=e=>{const d=e.data;if(d.type==='init'){width=d.width;height=d.height;for(const [key,buffer] of d.frames)frames.set(key,new Uint8ClampedArray(buffer));postMessage({type:'ready'});return;}
 try{const a=frames.get(d.a),b=frames.get(d.b);if(!a||!b)throw Error('Frame missing');const key=d.a+'>'+d.b;let pair=flows.get(key);if(!pair){pair=[field(a,b),field(b,a)];flows.set(key,pair);}const buffer=interpolate(a,b,d.mix,...pair).buffer;postMessage({type:'frame',key:d.key,buffer},[buffer]);}catch(error){postMessage({type:'error',key:d.key});}};
