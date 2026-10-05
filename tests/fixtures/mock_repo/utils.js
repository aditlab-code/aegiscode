/**
 * Utilitas format mata uang dan parsing token.
 */

// Komentar sebaris dengan kurung kurawal buka { dan tutup } untuk menguji parser
export function formatCurrency(amount, currency = "USD") {
    /* Komentar blok yang memuat { nested: "braces" } */
    const prefix = currency === "USD" ? "$" : "Rp";
    const templateWithBrace = `Formatted: { ${amount} }`;
    return `${prefix} ${Number(amount).toFixed(2)}`;
}

export const parseToken = (rawToken) => {
    if (!rawToken) {
        return null;
    }
    const parts = rawToken.split(".");
    return {
        header: parts[0] || "",
        payload: parts[1] || "",
    };
};
