// Объёмная оболочка общей симуляции. При отсутствии WebGL остаётся Canvas.
import * as THREE from './vendor/three.module.js';
const materials=new Map(),geometries=new Map();
function mat(color){if(!materials.has(color))materials.set(color,new THREE.MeshStandardMaterial({color,roughness:.55,metalness:.12}));return materials.get(color);}
function geo(type){if(!geometries.has(type))geometries.set(type,type==='box'?new THREE.BoxGeometry(1,1,1):type==='sphere'?new THREE.SphereGeometry(1,10,8):new THREE.CylinderGeometry(1,1,1,8));return geometries.get(type);}
function shape(parent,type,color,x,y,z,sx,sy,sz){const m=new THREE.Mesh(geo(type),mat(color));m.position.set(x,y,z);m.scale.set(sx,sy,sz);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
const box=(p,c,x,y,z,a,b,d)=>shape(p,'box',c,x,y,z,a,b,d);
const ball=(p,c,x,y,z,a,b=a,d=a)=>shape(p,'sphere',c,x,y,z,a,b,d);
const cylinder=(p,c,x,y,z,a,b,d=a)=>shape(p,'cylinder',c,x,y,z,a,b,d);
const textures=new Map();
function label(text,color='#ffffff',bg=null){const key=text+color+bg;if(!textures.has(key)){const c=document.createElement('canvas');c.width=256;c.height=128;const t=c.getContext('2d');if(bg){t.fillStyle=bg;t.fillRect(0,0,256,128);}t.font='900 70px system-ui';t.textAlign='center';t.textBaseline='middle';t.lineWidth=9;t.strokeStyle='#253c58';t.strokeText(String(text),128,68);t.fillStyle=color;t.fillText(String(text),128,68);const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;textures.set(key,tex);}
 const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:textures.get(key),transparent:true,depthWrite:false}));sprite.scale.set(2.4,1.2,1);return sprite;}
function ring(parent,color,r=.42){const m=new THREE.Mesh(new THREE.RingGeometry(r*.88,r,20),new THREE.MeshBasicMaterial({color,side:THREE.DoubleSide,transparent:true,opacity:.8}));m.rotation.x=-Math.PI/2;m.position.y=.035;parent.add(m);return m;}
function fighter(leader=false){const g=new THREE.Group();ring(g,0x88ff78,.45);const shirt=leader?'#f6c948':'#16d5ee';
 // Раздельные ноги и оружие создают читаемый силуэт, а не плоскую иконку.
 const legs=[];for(const side of [-1,1]){const leg=box(g,'#30435e',side*.15,.3,0,.19,.5,.22);legs.push(leg);box(g,'#f4fbff',side*.15,.08,.08,.22,.13,.35);}box(g,shirt,0,.85,0,.6,.66,.36);box(g,'#ff4d57',0,.57,0,.65,.17,.4);box(g,'#f6fae7',0,.87,.2,.12,.5,.06);ball(g,'#e9b88e',0,1.4,0,.23,.26,.23);ball(g,leader?'#f7d45a':'#22334a',0,1.61,-.015,.24,.18,.25);box(g,'#1a4e71',0,1.43,.21,.4,.1,.06);
 for(const side of [-1,1]){const arm=box(g,'#f0c49b',side*.37,.95,.12,.16,.45,.19);arm.rotation.x=-.6;}box(g,'#f2c738',.3,.98,-.26,.18,.22,.68);box(g,'#34404c',.3,1,-.75,.1,.12,.48);g.userData.legs=legs;return g;}
function monster(type,kind){const g=new THREE.Group();const limbs=[];
 if(type==='fast'){ball(g,'#973c85',0,.5,0,.55,.35,.7);ball(g,'#46283e',0,.42,.55,.4,.24,.3);for(let i=0;i<4;i++)for(const side of [-1,1]){const leg=box(g,'#52243e',side*.65,.29,(i-1.5)*.32,.8,.1,.11);leg.rotation.z=side*.35;limbs.push(leg);}for(const side of [-1,1])ball(g,'#ffbc5b',side*.13,.51,.79,.08);}
 else if(type==='shaman'||kind==='lich'){
 const robe=new THREE.Mesh(new THREE.ConeGeometry(.6,1.5,8),mat('#8b45c6'));robe.position.y=.8;robe.castShadow=true;g.add(robe);ball(g,'#4a275c',0,1.55,0,.38);box(g,'#e8d5b0',0,1.5,.3,.42,.26,.08);for(const side of [-1,1])ball(g,'#fd6aff',side*.12,1.56,.37,.06);box(g,'#5e3677',.65,1,0,.09,2,.09);ball(g,'#e29aff',.65,2.05,0,.21);ring(g,0xbf74ff,.6);
 }else if(type==='armored'){
 box(g,'#6c8791',0,.92,0,1.05,1.1,.7);box(g,'#97adb0',0,1.67,0,.58,.5,.54);for(const side of [-1,1]){box(g,'#576d7c',side*.73,.85,0,.42,.85,.48);const l=box(g,'#546777',side*.3,.25,0,.4,.5,.43);limbs.push(l);box(g,'#7ffff0',side*.13,1.7,.29,.14,.08,.03);}box(g,'#86ffe5',0,1,.38,.12,.65,.04);
 }else{
 const bone=type==='skeleton',color=bone?'#dcd9bf':type==='boss'?'#ff743d':'#d83f54';
 for(const side of [-1,1]){const l=box(g,bone?'#d7d6b8':'#34384f',side*.23,.28,0,.25,.5,.3);limbs.push(l);ball(g,color,side*.52,.94,0,.23,.45,.25);}
 if(bone){box(g,color,0,.85,0,.14,.8,.15);for(let i=0;i<4;i++)box(g,color,0,.65+i*.14,0,.66,.07,.19);}else{ball(g,color,0,.97,0,.55,.6,.38);box(g,'#34364d',0,.54,0,.92,.22,.66);}
 ball(g,color,0,1.64,0,.37,.4,.32);for(const side of [-1,1]){box(g,bone?'#282b3c':'#ffec93',side*.14,1.73,.29,.14,.09,.05);if(!bone){const horn=new THREE.Mesh(new THREE.ConeGeometry(.12,.45,6),mat('#fff1ce'));horn.position.set(side*.3,1.99,0);horn.rotation.z=side*-.4;g.add(horn);}}
 if(!bone){ball(g,'#f5b389',0,1.51,.32,.22,.13,.12);box(g,'#25283a',0,2,0,.45,.2,.26);}else box(g,'#bc4056',0,1.98,0,.68,.09,.6);
 }
 g.userData.legs=limbs;return g;}
class BridgeRenderer{
 constructor(){
 this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));this.renderer.setSize(540,960,false);this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFShadowMap;this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.2;
 const el=this.renderer.domElement;el.id='world3d';el.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none;';document.querySelector('#frame').insertBefore(el,document.querySelector('#hud'));
 this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#a7eafa');this.scene.fog=new THREE.Fog('#a7eafa',47,100);this.camera=new THREE.PerspectiveCamera(47,9/16,.1,160);this.camera.position.set(0,23,22);this.camera.lookAt(0,0,-12);
 this.scene.add(new THREE.HemisphereLight('#e9ffff','#7b8cad',2.2));const sun=new THREE.DirectionalLight('#fff3d5',3.5);sun.position.set(-12,30,8);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);Object.assign(sun.shadow.camera,{left:-22,right:22,top:40,bottom:-38,near:1,far:90});sun.shadow.bias=-.001;this.scene.add(sun);
 this.world=new THREE.Group();this.scene.add(this.world);this.actors=new Map();this.gates=new Map();this.props=new Map();this.effectGroups=[];this.squad=[];this.squadGroup=new THREE.Group();this.world.add(this.squadGroup);
 this.buildBridge();this.vector=new THREE.Vector3();this.renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();this.failed=true;el.style.display='none';window.dojoRenderer=null;});
 }
 pos(x,y){return[(x-270)/25,0,(y-755)/24];}
 project(x,y){this.camera.updateMatrixWorld();this.vector.set(...this.pos(x,y)).project(this.camera);const a=(this.vector.x+1)*270,b=(1-this.vector.y)*480;this.vector.set(...this.pos(x+1,y)).project(this.camera);return{x:a,y:b,scale:(this.vector.x+1)*270-a};}
 buildBridge(){const sea=box(this.world,'#24c5e2',0,-2,-30,150,.2,230);sea.receiveShadow=false;box(this.world,'#eee8e7',0,-.28,-17,17,.5,72);
 for(const x of [-8.6,8.6]){box(this.world,'#f7fcff',x,.12,-17,.4,.7,72);box(this.world,'#8bd5ed',x,.8,-17,.12,.13,72);for(let z=-51;z<19;z+=2.8){box(this.world,'#c4d1da',x,.55,z,.14,1.1,.16);if(z%2<1)box(this.world,'#709bb0',x,-2,z,.7,4,.7);}}
 for(let z=-51;z<19;z+=3.3){const stripe=box(this.world,'#ffffff',0,.005,z,.11,.012,1.6);stripe.receiveShadow=false;}
 // Низкополигональные блики на воде.
 this.water=[];for(let i=0;i<140;i++){const side=i%2?-1:1,x=side*(10+(i*13%44)),z=-70+(i*7%100);const foam=box(this.world,i%3?'#80e4ed':'#c7f9fa',x,-1.86,z,.4+i%5*.3,.015,.06);foam.castShadow=false;this.water.push(foam);}
 }
 gate(gate){const g=new THREE.Group();for(const x of [-.85,.85])box(g,'#ffbd42',x,1.05,0,.1,2.1,.15);box(g,'#16c6fa',0,1.3,0,1.6,1.35,.1);box(g,'#8af4ff',0,2,0,1.7,.07,.13);const text=label('+'+gate.value);text.position.set(0,1.33,.11);text.scale.set(1.5,.75,1);g.add(text);return g;}
 crate(e){const g=new THREE.Group();box(g,'#cf8c3d',0,.7,0,1.5,1.3,1.25);box(g,'#f0b458',0,1.39,0,1.55,.13,1.3);for(const x of [-.48,.48]){box(g,'#c4d6d9',x,.75,.64,.09,1.4,.03);box(g,'#b2c8cd',x,1.47,0,.1,.04,1.3);}const text=label(String(Math.ceil(e.hp)));text.position.set(0,.78,.68);g.add(text);g.userData.text=text;g.userData.hp=e.hp;return g;}
 sync(map,items,builder,updater){const keep=new Set();for(const item of items){if(item.dead)continue;keep.add(item);let group=map.get(item);if(!group){group=builder(item);this.world.add(group);map.set(item,group);}group.position.set(...this.pos(item.x,item.y));updater?.(group,item);}for(const[item,group]of map)if(!keep.has(item)){this.world.remove(group);map.delete(item);}}
 render(g){if(this.failed)return;const t=g.time;
 this.sync(this.actors,g.enemies,e=>e.type==='crate'?this.crate(e):monster(e.type,e.kind),(group,e)=>{
 const size=e.type==='boss'?(e.kind==='lich'?2.3:2.5):e.type==='armored'?1.1:.9;group.scale.setScalar(size);if(e.type==='crate')group.scale.setScalar(1);
 group.position.y=Math.sin(t*6+(e.phase||0))*.04;
 if(e.type==='boss'){if(!group.userData.health){box(group,'#5e293b',0,2.65,0,2,.12,.12);group.userData.health=box(group,'#ff4747',0,2.66,.08,2,.1,.1);}group.userData.health.scale.x=Math.max(.01,2*e.hp/e.maxHp);}

 group.userData.legs?.forEach((leg,i)=>leg.rotation.x=Math.sin(t*8+i*3)*.18);
 if(e.type==='crate'&&group.userData.hp!==Math.ceil(e.hp)){group.remove(group.userData.text);group.userData.text.material.dispose();const text=label(String(Math.max(0,Math.ceil(e.hp))));text.position.set(0,.78,.68);group.add(text);group.userData.text=text;group.userData.hp=Math.ceil(e.hp);}
 });
 this.sync(this.gates,g.gates,e=>this.gate(e));
 this.sync(this.props,g.pickups,e=>{const p=new THREE.Group();const colors={sword:'#ffb338',star:'#38aaff',heart:'#60ee65',slow:'#c17cff',army:'#fae147',coin:'#ffd34b'};const orb=ball(p,colors[e.type],0,.45,0,.3);orb.material=new THREE.MeshStandardMaterial({color:colors[e.type],emissive:colors[e.type],emissiveIntensity:.4});ring(p,colors[e.type],.48);const beam=box(p,colors[e.type],0,1.4,0,.08,2.7,.08);beam.material=new THREE.MeshBasicMaterial({color:colors[e.type],transparent:true,opacity:.38});return p;},(p,e)=>{p.rotation.y=t;p.position.y=Math.sin(t*4)*.08;});
 while(this.squad.length<g.player.army+1){const f=fighter(this.squad.length===0);this.squad.push(f);this.squadGroup.add(f);}this.squad.forEach((f,i)=>{f.visible=i<=g.player.army;if(!f.visible)return;const row=i===0?-1:Math.floor((i-1)/6),col=i===0?0:((i-1)%6)-2.5;const pos=this.pos(g.player.x+col*19,g.player.y+26+row*24);f.position.set(...pos);f.userData.legs.forEach((l,j)=>l.rotation.x=Math.sin(t*9+i+j*3)*.12);});
 // Эффекты переиспользуются: число объектов ограничено текущим боем.
 for(const f of this.effectGroups){this.world.remove(f);f.geometry?.dispose();f.material?.dispose();}this.effectGroups=[];
 for(const shot of g.shots){const m=new THREE.Mesh(new THREE.BoxGeometry(.045,.045,shot.star?.45:1.25),new THREE.MeshBasicMaterial({color:shot.star?'#63ddff':'#fff58c'}));m.position.set(...this.pos(shot.x,shot.y));m.position.y=1;this.world.add(m);this.effectGroups.push(m);}
 for(const bolt of g.hazards){const m=new THREE.Mesh(geo('sphere'),new THREE.MeshBasicMaterial({color:'#d45bff'}));m.scale.set(.19,.2,.4);m.position.set(...this.pos(bolt.x,bolt.y));m.position.y=.6;this.world.add(m);this.effectGroups.push(m);}
 for(const e of g.enemies){const warning=e.type==='boss'?e.warning:e.castWarning;if(warning>0){const x=e.type==='boss'?e.attackX:e.castX,w=e.type==='boss'?124:56;const near=this.pos(x,CONFIG.playerY+30),far=this.pos(x,e.y);const m=new THREE.Mesh(new THREE.PlaneGeometry(w/25,near[2]-far[2]),new THREE.MeshBasicMaterial({color:e.kind==='lich'?'#c450fa':'#fa4550',transparent:true,opacity:.28,side:THREE.DoubleSide}));m.rotation.x=-Math.PI/2;m.position.set(near[0],.025,(near[2]+far[2])/2);this.world.add(m);this.effectGroups.push(m);}}
 this.water.forEach((m,i)=>m.scale.x=1+Math.sin(t*1.5+i)*.2);this.camera.position.x=g.shake?Math.sin(t*90)*g.shake*.012:0;this.camera.lookAt(0,0,-12);this.renderer.render(this.scene,this.camera);
 }
}
try{const renderer=new BridgeRenderer();window.dojoRenderer=renderer;}catch(error){console.warn('WebGL unavailable; Canvas renderer retained.');}
