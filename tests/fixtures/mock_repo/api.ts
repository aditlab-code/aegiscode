/**
 * Klien API dan definisi antarmuka TypeScript.
 */

export interface ApiResponse<T> {
    code: number;
    message: string;
    data: T;
}

export class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    public async fetchData<T>(endpoint: string): Promise<ApiResponse<T>> {
        const url = `${this.baseUrl}/${endpoint}`;
        return {
            code: 200,
            message: "OK",
            data: {} as T,
        };
    }
}
