"use strict";
const {parseArgs} = require("node:util");
const fs = require("node:fs/promises");
const path = require("node:path");
const assert = require("node:assert/strict");
const {values:args} = parseArgs({options:{
  playwright:{type:"string"}, browser:{type:"string"}, output:{type:"string"},
  port:{type:"string",default:"8765"}, "allow-external-tools":{type:"boolean",default:false}
  , "analysis-fixture":{type:"string"}, "exercise-agents":{type:"boolean",default:false}
}});
async function main(){
  if(!args["allow-external-tools"]||!args.playwright||!args.browser||!args.output)throw new Error("Explicit browser approval, module, executable and new output are required");
  await fs.mkdir(args.output,{recursive:false});
  const {chromium}=require(path.resolve(args.playwright));
  const browser=await chromium.launch({executablePath:path.resolve(args.browser),headless:true,chromiumSandbox:true});
  const errors=[];
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1080},locale:"ko-KR",timezoneId:"Asia/Seoul"});
    const origin=`http://127.0.0.1:${Number(args.port)}`;
    await context.route("**/*",route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
    const page=await context.newPage();
    page.on("pageerror",error=>errors.push(error.message));
    await page.goto(origin,{waitUntil:"domcontentloaded"});
    await page.waitForFunction(()=>document.querySelector("#connection").textContent.includes("로컬 연결됨"));
    assert.equal(await page.locator("#run-godot").isChecked(),false);
    async function submit(selector){
      const response=page.waitForResponse(value=>value.url()===origin+"/api/v1/jobs"&&value.request().method()==="POST");
      await page.locator(selector).click();
      const created=await (await response).json();
      await page.waitForFunction(prefix=>Array.from(document.querySelectorAll("#job-list tr")).some(row=>row.textContent.includes(prefix)&&row.querySelector(".status-succeeded")),created.id.slice(0,8));
      return created;
    }
    let builder=null,analysis=null;
    if(args["exercise-agents"]){
      await page.locator("#requirements").fill("2D arena with 2 enemies");
      await page.locator("#run-godot").check();
      builder=await submit('[data-launch="builder"]');
      assert.equal(builder.spec.operation,"build");
      assert.equal(builder.spec.authorized,true);
    }
    if(args["analysis-fixture"]){
      await page.locator("#analysis-tool").selectOption("jadx");
      await page.locator("#analysis-path").fill(path.resolve(args["analysis-fixture"]));
      await page.locator("#authorized").check();
      await page.locator("#trusted-input").check();
      analysis=await submit('[data-launch="reverse"]');
      assert.equal(analysis.spec.operation,"decompile");
      assert.equal(analysis.spec.parameters.tool,"jadx");
    }
    await page.locator("#seed").fill("7");
    const submitted=page.waitForResponse(response=>response.url()===origin+"/api/v1/jobs"&&response.request().method()==="POST");
    await page.locator('[data-launch="player"]').click();
    const job=await (await submitted).json();
    await page.waitForFunction(()=>{const image=document.querySelector("#preview");return !image.hidden&&image.complete&&image.naturalWidth===160;});
    await page.waitForFunction(prefix=>Array.from(document.querySelectorAll("#job-list tr")).some(row=>row.textContent.includes(prefix)&&row.textContent.includes("목표 달성")),job.id.slice(0,8));
    const image=await page.locator("#preview").evaluate(node=>({width:node.naturalWidth,height:node.naturalHeight}));
    assert.deepEqual(image,{width:160,height:112});
    assert.equal(await page.locator("#notice").isVisible(),false);
    assert.deepEqual(errors,[]);
    await page.screenshot({path:path.join(args.output,"dashboard.png"),fullPage:false});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(args.output,"dashboard-mobile.png"),fullPage:true});
    const result={passed:true,browser:await browser.version(),preview:image,page_errors:errors,player_goal_verified:true,job_id:job.id,builder_job_id:builder?.id||null,analysis_job_id:analysis?.id||null,external_ai_connected:false};
    await fs.writeFile(path.join(args.output,"results.json"),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
