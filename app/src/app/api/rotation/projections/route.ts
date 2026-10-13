import {checkInProjection,saveProjection} from '@/lib/rotation/allocation-server';
import {ApiError,apiError,protectedRoute,rateLimit,readBody,requireSameOrigin,response} from '@/lib/rotation/server';
export const dynamic='force-dynamic';export const runtime='nodejs';
export const POST=protectedRoute(async(request,user)=>{try{requireSameOrigin(request);await rateLimit(request,`projection:${user.id}`,60);const body=await readBody(request);if(body.kind==='save')return response({projection:await saveProjection(user,body)},201);if(body.kind==='checkin')return response({outcome:await checkInProjection(user,body.projectionId)});throw new ApiError('Choose save or checkin.');}catch(error){return apiError(error);}});
