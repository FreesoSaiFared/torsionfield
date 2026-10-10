//! CM-002: deterministic morphogenesis of document-derived glyph seeds.
//! Pure geometry. No networking, DOM access, dynamic allocation, or visual claims of evidence.
use core::f32::consts::TAU;
const MAX:usize=720;
const SAMPLES:usize=26;
static mut SEEDS:[[f32;3];MAX]=[[0.0;3];MAX];
static mut VERTICES:[f32;MAX*SAMPLES*3]=[0.0;MAX*SAMPLES*3];
static mut COUNT:usize=0;
#[inline] fn clip(x:f32)->f32{x.max(0.0).min(1.0)}
#[inline] fn easing(x:f32)->f32{let a=clip(x);a*a*(3.0-2.0*a)}
#[inline] fn mix(a:f32,b:f32,t:f32)->f32{a+(b-a)*t}
#[inline] fn h(mut x:u32)->f32{
 x^=x>>16;x=x.wrapping_mul(0x7feb352d);x^=x>>15;x=x.wrapping_mul(0x846ca68b);x^=x>>16;
 (x as f64/u32::MAX as f64) as f32
}
#[inline] fn cubic(a:f32,b:f32,c:f32,d:f32,u:f32)->f32{
 let v=1.0-u;v*v*v*a+3.0*v*v*u*b+3.0*v*u*u*c+u*u*u*d
}
#[no_mangle] pub extern "C" fn cm_capacity()->i32{MAX as i32}
#[no_mangle] pub extern "C" fn cm_samples()->i32{SAMPLES as i32}
#[no_mangle] pub extern "C" fn cm_count()->i32{unsafe{COUNT as i32}}
#[no_mangle] pub extern "C" fn cm_output_ptr()->i32{
 (&raw const VERTICES) as *const f32 as i32
}
#[no_mangle] pub extern "C" fn cm_clear(){unsafe{COUNT=0;}}
#[no_mangle] pub extern "C" fn cm_seed(x:f32,y:f32,group:i32)->i32{
 unsafe{
  if COUNT>=MAX{return -1}
  let i=COUNT;
  SEEDS[i]=[clip(x),clip(y),group.max(0).min(2) as f32];
  COUNT+=1;i as i32
 }
}
fn dancer(group:usize,u:f32,time:f32,strand:u32)->(f32,f32){
 let sway=(time*0.78).sin()*0.031;
 let lift=(time*1.4).cos()*0.026;
 let x=0.5+sway;
 match group{
  0=>match strand%5{
   0=>{let a=u*TAU;(x+0.063*a.cos(),0.255+0.08*a.sin())},
   1=>(cubic(x-0.045,0.36,0.21,0.13,u),cubic(0.385,0.27+lift,0.44,0.25+lift,u)),
   2=>(cubic(x+0.045,0.65,0.73,0.88,u),cubic(0.385,0.42,0.17+lift,0.22+lift,u)),
   3=>(cubic(x-0.02,0.35,0.33,0.43,u),cubic(0.20,0.12,0.3,0.41,u)),
   _=>(cubic(x-0.13,x-0.05,x+0.05,x+0.13,u),0.405+0.024*(u*TAU).sin())
  },
  1=>match strand%4{
   0=>(x+0.02*(u*TAU*2.4).sin()*(1.0-u),0.39+0.25*u),
   1=>(x+0.076*(u*TAU*2.0).sin(),0.42+0.20*u),
   2=>(x+0.09*(u*TAU).cos(),0.54+0.075*(u*TAU).sin()),
   _=>(x+0.05*(u*TAU*4.5).sin()*(1.0-u),0.39+0.25*u)
  },
  _=>if strand%2==0{
   (cubic(x-0.015,0.4,0.28,0.21,u),cubic(0.625,0.70,0.84,0.94,u)+lift*u)
  }else{
   (cubic(x+0.015,0.66,0.76,0.84,u),cubic(0.625,0.70,0.86,0.94,u)-lift*u)
  }
 }
}
fn graph(group:usize,u:f32,revision:i32,lambda:f32,strand:u32)->(f32,f32){
 let center=(0.51,0.49);
 let (a,b,c)=match group{
  0=>(0.18,0.29,0.33),
  1=>(0.80,0.27,0.66),
  _=>(0.78,0.79,0.65),
 };
 let pull=(lambda-0.4)*0.06;
 let branch=strand%6;
 if branch>=4{
  let point=if branch==4{(a,b)}else{center};
  let radius=if branch==4{0.057}else{0.095};
  let theta=u*TAU;
  return (point.0+radius*theta.cos(),point.1+radius*theta.sin()*0.8)
 }
 let bow=(branch as f32-1.5)*0.026;
 let x=cubic(a+pull,c+bow,center.0-bow,center.0,u);
 let y=cubic(b,b-0.19+bow,center.1+bow,center.1,u);
 let disputed=if revision>1&&group==2{0.034*(u*TAU*2.0).sin()}else{0.0};
 (x+disputed,y-disputed*0.54)
}
#[inline] fn field(x:f32,y:f32,t:f32,seed:f32)->(f32,f32){
 let a=(x*12.1+t*0.53+seed*6.0).sin()*(y*9.3-t*0.32).cos();
 let b=(y*14.5-t*0.41+seed*3.0).cos()*(x*10.1+t*0.61).sin();
 let c=(x*5.3-y*7.1+t*0.87+seed).sin();
 ((a+b*0.54+c*0.31)*0.009,(b-a*0.62-c*0.36)*0.009)
}
#[no_mangle] pub extern "C" fn cm_build(t:f32,lambda:f32,revision:i32,mouse_x:f32,mouse_y:f32,pull:f32)->i32{
 let t=t.max(0.0).min(20.0);
 let gather=easing((t-1.2)/5.2);
 let to_graph=easing((t-9.5)/4.8);
 let restore=easing((t-17.0)/3.0);
 let expressive=easing((t-1.8)/3.7)*(1.0-easing((t-16.5)/3.2));
 unsafe{
  for i in 0..COUNT{
   let [sx,sy,g]=SEEDS[i];let group=g as usize;
   let jitter=h((i as u32).wrapping_mul(3239)+17);
   let spread=h((i as u32).wrapping_mul(5167)+71)-0.5;
   let base_u=h((i as u32).wrapping_mul(1201)+53);
   for j in 0..SAMPLES{
    let v=j as f32/(SAMPLES-1) as f32;
    let u=clip(base_u+(v-0.5)*(0.10+spread.abs()*0.13));
    let (dx,dy)=dancer(group,u,t,i as u32);
    let (gx,gy)=graph(group,u,revision,lambda,i as u32);
    let orbit=TAU*(t*0.09+jitter*0.5+v*0.44);
    let spiral=0.075*(1.0-gather)*(t*0.4).sin();
    let ox=sx+(v-0.5)*0.012+spiral*orbit.cos();
    let oy=sy+(v-0.5)*0.004+spiral*orbit.sin();
    let mut x=mix(ox,dx,gather);
    let mut y=mix(oy,dy,gather);
    x=mix(x,gx,to_graph);y=mix(y,gy,to_graph);
    x=mix(x,sx+(v-0.5)*0.012,restore);
    y=mix(y,sy+(v-0.5)*0.004,restore);
    let (fx,fy)=field(x,y,t,jitter);
    let turbulence=expressive*(0.35+0.65*(1.0-to_graph))*(0.6+lambda*0.6);
    x+=fx*turbulence+spread*0.011*expressive*(v*TAU*3.0+t*0.65).sin();
    y+=fy*turbulence+spread*0.012*expressive*(v*TAU*2.0-t*0.43).cos();
    let mx=x-mouse_x;let my=y-mouse_y;let dist2=mx*mx+my*my;
    let pressure=if pull>0.0{pull.min(1.0)*(-dist2/0.035).exp()}else{0.0};
    x+=mx*pressure*0.42;y+=my*pressure*0.42;
    let index=(i*SAMPLES+j)*3;
    VERTICES[index]=x;VERTICES[index+1]=y;
    VERTICES[index+2]=(0.30+0.55*(v*TAU).sin().abs())*(0.24+0.76*expressive)*(1.0-restore*0.28);
   }
  }
  COUNT as i32
 }
}
