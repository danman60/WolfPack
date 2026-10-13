import {advanceAllocation,applyAllocation,loadBatch} from '@/lib/rotation/allocation-server';
import {ApiError,apiError,getPortfolio,protectedRoute,rateLimit,readBody,requireSameOrigin,response} from '@/lib/rotation/server';
export const dynamic='force-dynamic';export const runtime='nodejs';
export const GET=protectedRoute(async(request,user)=>{try{return response({batch:await loadBatch(user,new URL(request.url).searchParams.get('id')),portfolio:await getPortfolio(user)});}catch(error){return apiError(error);}});
export const POST=protectedRoute(async(request,user)=>{try{requireSameOrigin(request);await rateLimit(request,`batch:${user.id}`,120);const body=await readBody(request);if(body.kind==='apply')return response(await applyAllocation(user,body));if(['advance','pause','resume','cancel'].includes(String(body.kind)))return response(await advanceAllocation(user,body));throw new ApiError('Unknown batch action.');}catch(error){return apiError(error);}});
