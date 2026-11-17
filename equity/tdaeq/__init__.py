"""Shared code for the equity TDA study.

data       load the 200-stock panel, sectors and VIX
factors    remove the market, standardise, turn correlations into distances
clusters   peer groups (single linkage = H0, average linkage, sectors, HDBSCAN)
topology   persistence diagrams, summaries, diagram distances, noise nulls
portfolio  the neutral reversal book
evaluate   block bootstrap, performance numbers, rank correlation
"""
