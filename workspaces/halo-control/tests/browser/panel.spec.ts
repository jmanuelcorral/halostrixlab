import {test,expect} from '@playwright/test';

test('preview fails closed without Cockpit',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Resumen',exact:true})).toBeVisible();
  await expect(page.getByText('Vista previa sin sesión.',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Arrancar gateway',exact:true})).toBeDisabled();
  await page.getByRole('navigation').getByRole('button',{name:/Terminal/}).click();
  await expect(page.getByRole('button',{name:'Abrir consola',exact:true})).toBeDisabled();
});

test('authenticated fixture uses direct actions and the remote ComfyUI link',async({page})=>{
  await page.route('**/runtime.json',route=>route.fulfill({json:{workspace:'/fixture'}}));
  await page.addInitScript(()=>{
    const history=Array.from({length:20},(_,index)=>({time:Date.now()/1000-(20-index)*5,cpu:{cpu:25+index},memory:{used:40*2**30,total:128*2**30,available:88*2**30,swap_used:0},gpu:[{device:'card0',busy:60,gtt_used:33*2**30,gtt_total:62*2**30,vram_used:0,watts:80}],temperatures:[{sensor:'k10temp:Tctl',celsius:72,critical:95}],disk:{free:1000*2**30,total:2000*2**30},network:{eth0:{rx:1024,tx:2048}},pressure:{cpu:{some:{avg10:0}}},load:[1,2,3]}));
    (window as any).actions=[];
    (window as any).cockpit={spawn:async(args:string[])=>{
      if(args[2]==='submit'){
        (window as any).actions.push(args[3]);
        await new Promise(resolve=>setTimeout(resolve,150));
        return JSON.stringify({job:'fixture'});
      }
      return JSON.stringify(args[2]==='history'?history:args[2]==='logs'?{text:'<script>not executed</script>'}:{services:{gateway:'active',comfyui:'active',metrics:'active'},halogen:'loaded',gateway_health:true,gateway_ui_url:'http://192.168.10.20:18080/ui/',comfyui_health:true,comfyui_url:'http://192.168.10.20:8188',unsloth:{available:true,state:'running',health:true,url:'http://192.168.10.20:8888',error:''},llamafactory:{available:true,state:'running',health:false,url:'http://192.168.10.20:7860',error:''},jobs:[],errors:[],ssh_hosts:[],boot_id:'fixture',maintenance_available:false});
    },user:async()=>({name:'fixture',home:'/tmp',shell:'/bin/bash'})};
  });
  await page.goto('/');
  await expect(page.getByText('40.0 GiB',{exact:true})).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  const gatewayLink=page.getByRole('link',{name:'Abrir interfaz llama-swap ↗'});
  await expect(gatewayLink).toHaveAttribute('href','http://192.168.10.20:18080/ui/');
  await expect(gatewayLink).toHaveAttribute('target','_blank');
  await expect(page.getByRole('link',{name:'Abrir interfaz ComfyUI ↗'})).toHaveAttribute('href','http://192.168.10.20:8188');
  await expect(page.getByRole('heading',{name:'Unsloth Studio',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Abrir interfaz Unsloth Studio ↗'})).toHaveAttribute('href','http://192.168.10.20:8888');
  await expect(page.getByRole('button',{name:'Arrancar Studio',exact:true})).toBeEnabled();
  await expect(page.getByRole('heading',{name:'LLaMA-Factory',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Abrir interfaz LlamaBoard ↗'})).toHaveAttribute('href','http://192.168.10.20:7860');
  await expect(page.getByRole('button',{name:'Arrancar LlamaBoard',exact:true})).toBeEnabled();
  await expect(page.getByText('http://192.168.10.20:7860 · HTTP pendiente de comprobación', {exact:true})).toBeVisible();
  const imagesOn = page.locator('article.service').filter({has:page.getByRole('heading',{name:'ComfyUI',exact:true})}).getByRole('button',{name:'ON graceful',exact:true});
  const textOn = page.locator('article.service').filter({has:page.getByRole('heading',{name:'Halogen',exact:true})}).getByRole('button',{name:'ON graceful',exact:true});
  await expect(textOn).toBeEnabled();
  await imagesOn.click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('Operación registrada');
  expect(await page.evaluate(()=>(window as any).actions)).toEqual(['switch-images']);
  await expect(imagesOn).toBeDisabled();
  await expect(textOn).toBeDisabled();
  await page.screenshot({path:'data/dashboard-test.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'Resumen',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
