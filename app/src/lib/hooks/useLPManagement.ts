"use client";

import { useCallback } from "react";
import {
  useWriteContract,
  useWaitForTransactionReceipt,
  useReadContract,
  useAccount,
} from "wagmi";
import { parseUnits, maxUint128 } from "viem";
import { NONFUNGIBLE_POSITION_MANAGER_ABI, NONFUNGIBLE_POSITION_MANAGER_ADDRESS } from "@/lib/abis/NonfungiblePositionManager";
import { ERC20_ABI } from "@/lib/abis/ERC20";

const NFT_MANAGER = NONFUNGIBLE_POSITION_MANAGER_ADDRESS[1];

// ---------------------------------------------------------------------------
// Collect Fees
// ---------------------------------------------------------------------------

export function useCollectFees() {
  const { address } = useAccount();
  const { writeContract, data: hash, isPending, error } = useWriteContract();
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash });

  const collect = useCallback(
    (tokenId: bigint) => {
      if (!address) return;
      writeContract({
        address: NFT_MANAGER,
        abi: NONFUNGIBLE_POSITION_MANAGER_ABI,
        functionName: "collect",
        args: [
          {
            tokenId,
            recipient: address,
            amount0Max: maxUint128,
            amount1Max: maxUint128,
          },
        ],
      });
    },
    [address, writeContract]
  );

  return { collect, isPending, isConfirming, isSuccess, error, hash };
}

// ---------------------------------------------------------------------------
// Remove Liquidity (decrease + collect)
// ---------------------------------------------------------------------------

export function useRemoveLiquidity() {
  const { address } = useAccount();
  const { writeContract, data: hash, isPending, error } = useWriteContract();
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash });

  const removeLiquidity = useCallback(
    (tokenId: bigint, liquidity: bigint) => {
      if (!address) return;
      writeContract({
        address: NFT_MANAGER,
        abi: NONFUNGIBLE_POSITION_MANAGER_ABI,
        functionName: "decreaseLiquidity",
        args: [
          {
            tokenId,
            liquidity: BigInt(liquidity),
            amount0Min: 0n,
            amount1Min: 0n,
            deadline: BigInt(Math.floor(Date.now() / 1000) + 1800), // 30 min
          },
        ],
      });
    },
    [address, writeContract]
  );

  return { removeLiquidity, isPending, isConfirming, isSuccess, error, hash };
}

// ---------------------------------------------------------------------------
// Approve Token
// ---------------------------------------------------------------------------

export function useApproveToken(tokenAddress: `0x${string}` | undefined) {
  const { writeContract, data: hash, isPending, error } = useWriteContract();
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash });

  const approve = useCallback(
    (amount: bigint) => {
      if (!tokenAddress) return;
      writeContract({
        address: tokenAddress,
        abi: ERC20_ABI,
        functionName: "approve",
        args: [NFT_MANAGER, amount],
      });
    },
    [tokenAddress, writeContract]
  );

  return { approve, isPending, isConfirming, isSuccess, error, hash };
}

// ---------------------------------------------------------------------------
// Check Allowance
// ---------------------------------------------------------------------------

export function useAllowance(
  tokenAddress: `0x${string}` | undefined,
  owner: `0x${string}` | undefined
) {
  return useReadContract({
    address: tokenAddress,
    abi: ERC20_ABI,
    functionName: "allowance",
    args: owner ? [owner, NFT_MANAGER] : undefined,
    query: { enabled: !!tokenAddress && !!owner },
  });
}

// ---------------------------------------------------------------------------
// Mint New Position
// ---------------------------------------------------------------------------

export function useMintPosition() {
  const { address } = useAccount();
  const { writeContract, data: hash, isPending, error } = useWriteContract();
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash });

  const mint = useCallback(
    (params: {
      token0: `0x${string}`;
      token1: `0x${string}`;
      fee: number;
      tickLower: number;
      tickUpper: number;
      amount0: bigint;
      amount1: bigint;
    }) => {
      if (!address) return;
      writeContract({
        address: NFT_MANAGER,
        abi: NONFUNGIBLE_POSITION_MANAGER_ABI,
        functionName: "mint",
        args: [
          {
            token0: params.token0,
            token1: params.token1,
            fee: params.fee,
            tickLower: params.tickLower,
            tickUpper: params.tickUpper,
            amount0Desired: params.amount0,
            amount1Desired: params.amount1,
            amount0Min: 0n,
            amount1Min: 0n,
            recipient: address,
            deadline: BigInt(Math.floor(Date.now() / 1000) + 1800),
          },
        ],
      });
    },
    [address, writeContract]
  );

  return { mint, isPending, isConfirming, isSuccess, error, hash };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert a human-readable amount to token units */
export function toTokenUnits(amount: string, decimals: number): bigint {
  try {
    return parseUnits(amount, decimals);
  } catch {
    return 0n;
  }
}

/** Calculate tick from price for a given pool */
export function priceToTick(price: number, token0Decimals: number, token1Decimals: number): number {
  // tick = log(price * 10^(d0-d1)) / log(1.0001)
  const adjustedPrice = price * Math.pow(10, token0Decimals - token1Decimals);
  if (adjustedPrice <= 0) return 0;
  return Math.floor(Math.log(adjustedPrice) / Math.log(1.0001));
}

/** Calculate price from tick */
export function tickToPrice(tick: number, token0Decimals: number, token1Decimals: number): number {
  return Math.pow(1.0001, tick) / Math.pow(10, token0Decimals - token1Decimals);
}

/** Round tick to nearest valid tick spacing */
export function roundTick(tick: number, tickSpacing: number): number {
  return Math.round(tick / tickSpacing) * tickSpacing;
}
