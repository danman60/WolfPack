import type {AllocationWorkspace} from './allocation-contract';
/** Private spot adapters must implement intent lookup before retry; paper is a separate account. */
export type NativeOrderState = {clientOrderId:string;status:'unknown'|'open'|'partial'|'filled'|'rejected';exchangeOrderId?:string};
export interface NativeExecutionAdapter {
  provider: string;
  connectedAccount(): Promise<{id:string;withdrawalsEnabled:boolean}>;
  lookup(clientOrderId:string): Promise<NativeOrderState>;
  submit(intent:{clientOrderId:string;market:string;side:'buy'|'sell';quantity:string;limitPrice:string}):Promise<NativeOrderState>;
}
export function executionConnection(): AllocationWorkspace['connection'] {
  return {mode:'paper',provider:'paper',connected:false,supportedRoutes:['BTC/CAD','ETH/CAD','LINK/CAD'],note:'This account executes simulated fills against real Ndax CAD books. No private exchange account is connected; analytical cross-pairs are not execution markets.'};
}
