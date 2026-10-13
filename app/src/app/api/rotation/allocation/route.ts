import {allocationWorkspace,saveAllocationSettings} from '@/lib/rotation/allocation-server';
import {ApiError,apiError,protectedRoute,rateLimit,readBody,requireSameOrigin,response} from '@/lib/rotation/server';
export const dynamic='force-dynamic';export const runtime='nodejs';
export const GET=protectedRoute(async(_request,user)=>{try{return response(await allocationWorkspace(user));}catch(error){return apiError(error);}});

export const POST=protectedRoute(async(request,user)=>{try{requireSameOrigin(request);await rateLimit(request,`allocation-settings:${user.id}`,30);const body=await readBody(request);if(body.kind!=="settings")throw new ApiError("Choose settings.");return response(await saveAllocationSettings(user,body));}catch(error){return apiError(error);}});
