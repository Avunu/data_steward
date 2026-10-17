// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Global jailbreak object for capability checking
window.jailbreak = {
	/**
	 * Check if a jailbreak capability is enabled (for UI decisions)
	 * @param {JailbreakCapability} capability - The capability to check
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
					resolve(Boolean(r.message));
				},
				error: function () {
					resolve(false);
				},
			});
		});
	},
};
