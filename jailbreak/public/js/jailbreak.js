// Global jailbreak object for capability checking
window.jailbreak = {
	/**
	 * Check if a jailbreak capability is enabled (for UI decisions)
	 * @param {string} capability - The capability to check
	 * @returns {Promise<boolean>} - Promise that resolves to true if enabled, false otherwise
	 */
	check_capability: function (capability) {
		return new Promise((resolve) => {
			frappe.call({
				method: "jailbreak.api.check_capability",
				args: {
					capability: capability,
				},
				callback: function (r) {
					resolve(r.message || false);
				},
				error: function () {
					resolve(false);
				},
			});
		});
	},
};
